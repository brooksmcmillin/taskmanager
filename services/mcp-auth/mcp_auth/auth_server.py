import asyncio
import json
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, cast

import aiohttp
import click
from dotenv import load_dotenv
from mcp.server.auth.provider import AccessTokenT, AuthorizationCodeT, RefreshTokenT
from mcp.server.auth.routes import cors_middleware, create_auth_routes
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from taskmanager_sdk import AuthenticationError, TaskManagerClient, TokenConfig
from uvicorn import Config, Server

from .responses import (
    backend_connection_error,
    backend_invalid_response,
    backend_timeout,
    invalid_client,
    invalid_request,
    rate_limit_exceeded,
    server_error,
    slow_down,
)
from .taskmanager_oauth_provider import TaskManagerAuthSettings, TaskManagerOAuthProvider
from .token_storage import TokenStorage

load_dotenv()
logger = logging.getLogger(__name__)

# Constants for device flow
DEVICE_CODE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"

# Input validation patterns (alphanumeric, hyphens, underscores)
VALID_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,256}$")


class RateLimiter:
    """
    Simple in-memory rate limiter for OAuth endpoints.

    Tracks requests per client within a sliding time window.
    Thread-safe for async usage within a single process.
    """

    def __init__(self, requests_per_window: int, window_seconds: int):
        self.requests_per_window = requests_per_window
        self.window_seconds = window_seconds
        self.clients: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str) -> bool:
        """Check if the client is allowed to make a request."""
        now = time.time()
        # Clean old requests outside the window
        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id] if now - req_time < self.window_seconds
        ]

        if len(self.clients[client_id]) >= self.requests_per_window:
            return False

        self.clients[client_id].append(now)
        return True

    def get_retry_after(self, client_id: str) -> int:
        """Get the number of seconds until the client can retry."""
        if not self.clients[client_id]:
            return 0
        oldest_request = min(self.clients[client_id])
        retry_after = int(self.window_seconds - (time.time() - oldest_request)) + 1
        return max(retry_after, 1)


# Rate limiters for device flow endpoints
# Device code requests: 10 requests per hour per client
device_code_limiter = RateLimiter(requests_per_window=10, window_seconds=3600)
# Token polling: 60 requests per 5 minutes per client (allows ~5 second intervals)
token_poll_limiter = RateLimiter(requests_per_window=60, window_seconds=300)


class TaskManagerAuthProvider(
    TaskManagerOAuthProvider[AuthorizationCodeT, RefreshTokenT, AccessTokenT]
):
    """
    Authorization Server provider that integrates with TaskManager OAuth.

    This provider:
    1. Delegates OAuth authentication to TaskManager endpoints
    2. Issues MCP tokens after TaskManager authentication
    3. Stores token state for introspection by Resource Servers
    """

    def __init__(
        self,
        auth_settings: TaskManagerAuthSettings,
        server_url: str,
        token_storage: TokenStorage | None = None,
    ):
        super().__init__(auth_settings, server_url, token_storage=token_storage)
        self.registered_clients: dict[str, Any] = {}


# API client for backend database operations
api_client: TaskManagerClient | None = None

# Store credentials for re-authentication when token expires
_api_credentials: dict[str, str] | None = None


def ensure_valid_api_client() -> TaskManagerClient | None:
    """
    Ensure the API client has a valid (non-expired) token.

    Client Credentials tokens expire after 1 hour. This function checks if
    the token is expired (or about to expire) and re-authenticates if needed.

    Returns:
        Valid TaskManagerClient or None if credentials are not configured.
    """
    global api_client, _api_credentials
    from taskmanager_sdk import create_client_credentials_client

    if not _api_credentials:
        return api_client

    # Check if token is expired or will expire within 5 minutes
    if (
        api_client
        and api_client.token_expires_at
        and time.time() < api_client.token_expires_at - TokenConfig.TOKEN_REFRESH_BUFFER_SECONDS
    ):
        return api_client

    # Token expired or about to expire, re-authenticate
    logger.info("API client token expired or missing, re-authenticating...")
    try:
        api_client = create_client_credentials_client(
            _api_credentials["client_id"],
            _api_credentials["client_secret"],
            _api_credentials["base_url"],
        )
        logger.info("API client re-authenticated successfully")
    except Exception as e:
        logger.error(f"Failed to re-authenticate API client: {e}")
        return None

    return api_client


def parse_json_field(value: Any, default: Any) -> Any:
    """Parse a JSON string field, returning the value as-is if not a string.

    Args:
        value: The value to parse (may be a JSON string, list, or other type)
        default: Default value to return if parsing fails or value is falsy

    Returns:
        Parsed value or default
    """
    if not value:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def parse_scope_field(scopes: Any) -> str:
    """Parse OAuth scope field into a space-separated string.

    Handles multiple formats:
    - List of strings: ["read", "write"] -> "read write"
    - JSON string array: '["read", "write"]' -> "read write"
    - Space-separated string: "read write" -> "read write"

    Args:
        scopes: Scope value in any supported format

    Returns:
        Space-separated scope string
    """
    if not scopes:
        return "read"
    if isinstance(scopes, list):
        return " ".join(scopes)
    if isinstance(scopes, str) and scopes.startswith("["):
        try:
            parsed = json.loads(scopes)
            return " ".join(parsed) if isinstance(parsed, list) else scopes
        except json.JSONDecodeError:
            return scopes
    return scopes


def transform_client_data(client_data: dict[str, Any]) -> dict[str, Any] | None:
    """Transform backend client data to OAuth server format.

    Args:
        client_data: Raw client data from backend API

    Returns:
        Transformed client dict, or None if client_id is missing
    """
    client_id = client_data.get("client_id") or client_data.get("clientId")
    if not client_id:
        return None

    # Parse JSON string fields
    redirect_uris = parse_json_field(
        client_data.get("redirect_uris") or client_data.get("redirectUris"),
        default=[],
    )
    grant_types = parse_json_field(
        client_data.get("grant_types") or client_data.get("grantTypes"),
        default=["authorization_code", "refresh_token"],
    )
    response_types = parse_json_field(
        client_data.get("response_types"),
        default=["code"],
    )

    # Parse scope field (handles multiple formats)
    scope_string = parse_scope_field(client_data.get("scope") or client_data.get("scopes"))

    # Determine auth method based on client name
    # Clients with "claude-code" in their name are public clients (no secret)
    client_name = client_data.get("name", "")
    auth_method = "none" if "claude-code" in client_name else "client_secret_post"

    # Don't set client_secret for public clients
    client_secret = (
        None
        if auth_method == "none"
        else (client_data.get("client_secret") or client_data.get("clientSecret", "dummy-secret"))
    )

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uris": redirect_uris,
        "response_types": response_types,
        "grant_types": grant_types,
        "token_endpoint_auth_method": auth_method,
        "scope": scope_string,
        "created_at": client_data.get("created_at") or int(time.time()),
    }


def load_registered_clients() -> dict[str, Any]:
    """Load registered clients from backend database."""
    client = ensure_valid_api_client()
    if not client:
        return {}

    response = client.get_oauth_clients()
    if not response.success:
        logging.warning(f"Could not load clients from backend: {response.error}")
        return {}

    if not response.data:
        return {}

    logger.info(f"Loaded {len(response.data)} clients from backend database")
    clients = {}

    for client_data in response.data:
        logger.debug(f"Processing client data: {client_data}")
        processed = transform_client_data(client_data)
        if processed:
            client_id = processed["client_id"]
            logger.info(
                f"Processed client {client_id} with scope: '{processed['scope']}', "
                f"auth_method: '{processed['token_endpoint_auth_method']}'"
            )
            clients[client_id] = processed

    return clients


# Load persisted client storage
registered_clients = {}


async def handle_device_code_token_exchange(
    parsed_body: dict[str, list[str]],
    oauth_provider: "TaskManagerAuthProvider",  # type: ignore[type-arg]
    auth_settings: TaskManagerAuthSettings,
) -> Response:
    """
    Handle device_code grant type token exchange (RFC 8628).

    This function proxies the device code token exchange to TaskManager,
    and if successful, issues an MCP token for the client.

    Security features:
    - Input validation for device_code and client_id
    - Rate limiting to prevent brute-force attacks
    - Client authentication validation for confidential clients
    - Request timeouts to prevent blocking
    - Proper error handling for backend failures
    """
    device_code = parsed_body.get("device_code", [""])[0]
    client_id = parsed_body.get("client_id", [""])[0]
    client_secret = parsed_body.get("client_secret", [""])[0]

    logger.debug(f"Device code token exchange initiated for client: {client_id}")

    # === Input Validation ===
    if not device_code:
        return invalid_request("device_code is required")

    if not client_id:
        return invalid_request("client_id is required")

    # Validate input format to prevent injection attacks
    if not VALID_ID_PATTERN.match(client_id):
        logger.warning("Invalid client_id format in device token exchange")
        return invalid_request("Invalid client_id format")

    if not VALID_ID_PATTERN.match(device_code):
        logger.warning(f"Invalid device_code format from client: {client_id}")
        return invalid_request("Invalid device_code format")

    # === Rate Limiting ===
    if not token_poll_limiter.is_allowed(client_id):
        retry_after = token_poll_limiter.get_retry_after(client_id)
        logger.warning(f"Rate limit exceeded for client: {client_id}")
        return slow_down("Polling too frequently", retry_after)

    # === Client Authentication Validation ===
    # Check if client exists and validate authentication requirements
    client = oauth_provider.registered_clients.get(client_id)
    if client:
        auth_method = client.get("token_endpoint_auth_method", "client_secret_post")

        # If client requires authentication, validate the secret
        if auth_method != "none":
            if not client_secret:
                logger.warning(f"Missing client_secret for confidential client: {client_id}")
                return invalid_client("client_secret required")

            expected_secret = client.get("client_secret")
            # Use constant-time comparison to prevent timing attacks
            if expected_secret and not secrets.compare_digest(
                client_secret.encode("utf-8") if client_secret else b"",
                expected_secret.encode("utf-8"),
            ):
                logger.warning(f"Invalid client_secret for client: {client_id}")
                return invalid_client("Invalid client credentials")

    # === Proxy to TaskManager with timeout ===
    timeout = aiohttp.ClientTimeout(total=TokenConfig.HTTP_REQUEST_TIMEOUT_SECONDS)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            token_data = {
                "grant_type": DEVICE_CODE_GRANT_TYPE,
                "device_code": device_code,
                "client_id": client_id,
            }
            # Only include client_secret if provided (for backend validation)
            if client_secret:
                token_data["client_secret"] = client_secret

            token_url = f"{auth_settings.base_url}/api/oauth/token"
            logger.debug("Proxying device token request to TaskManager")

            async with session.post(token_url, data=token_data) as resp:
                # Handle non-JSON responses gracefully
                try:
                    response_data = await resp.json()
                except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                    logger.error(f"Invalid JSON response from TaskManager: {e}")
                    return backend_invalid_response()

                # Validate response is a dict
                if not isinstance(response_data, dict):
                    logger.error(
                        f"Unexpected response type from TaskManager: {type(response_data)}"
                    )
                    return backend_invalid_response()

                logger.debug(f"TaskManager device token response status: {resp.status}")

                # If not successful, forward the error response
                # This includes authorization_pending, slow_down, expired_token, access_denied
                if resp.status != 200:
                    return JSONResponse(
                        response_data,
                        status_code=resp.status,
                        headers={"Cache-Control": "no-store"},
                    )

                # TaskManager returned an access token - now issue an MCP token
                taskmanager_token = response_data.get("access_token")
                if not taskmanager_token:
                    logger.error("No access_token in successful TaskManager response")
                    return server_error("No access token from backend")

                # Generate MCP access token
                mcp_token = f"mcp_{secrets.token_hex(32)}"
                expires_at = int(time.time()) + TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS

                # Get scopes from response or use default
                scope_str = response_data.get("scope", auth_settings.mcp_scope)
                scopes = scope_str.split() if scope_str else [auth_settings.mcp_scope]

                # Store MCP token in database if available
                if oauth_provider.token_storage:
                    await oauth_provider.token_storage.store_token(
                        token=mcp_token,
                        client_id=client_id,
                        scopes=scopes,
                        expires_at=expires_at,
                        resource=None,
                    )
                    logger.debug("Stored MCP token from device flow in database")
                else:
                    # Fall back to in-memory storage
                    from mcp.server.auth.provider import AccessToken

                    oauth_provider.tokens[mcp_token] = AccessToken(
                        token=mcp_token,
                        client_id=client_id,
                        scopes=scopes,
                        expires_at=expires_at,
                        resource=None,
                    )
                    logger.debug("Stored MCP token from device flow in memory")

                # Return MCP token response
                mcp_response: dict[str, str | int] = {
                    "access_token": mcp_token,
                    "token_type": "Bearer",
                    "expires_in": TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS,
                    "scope": " ".join(scopes),
                }

                # Include refresh token if TaskManager provided one
                if response_data.get("refresh_token"):
                    mcp_response["refresh_token"] = response_data["refresh_token"]

                logger.info(f"Issued MCP token for device flow to client: {client_id}")
                return JSONResponse(
                    mcp_response, status_code=200, headers={"Cache-Control": "no-store"}
                )

    except TimeoutError:
        logger.error("Timeout connecting to TaskManager for device token exchange")
        return backend_timeout()
    except aiohttp.ClientError as e:
        logger.error(f"Connection error to TaskManager: {e}")
        return backend_connection_error()


def create_authorization_server(
    host: str,
    port: int,
    server_url: AnyHttpUrl,
    auth_settings: TaskManagerAuthSettings,
    token_storage: TokenStorage | None = None,
) -> Starlette:
    """Create the Authorization Server application."""
    oauth_provider = TaskManagerAuthProvider(  # type: ignore[var-annotated]
        auth_settings, str(server_url), token_storage=token_storage
    )

    # Load and share registered clients with OAuth provider
    global registered_clients
    registered_clients = load_registered_clients()
    oauth_provider.registered_clients = registered_clients

    mcp_auth_settings = AuthSettings(
        issuer_url=server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[auth_settings.mcp_scope],
            default_scopes=[auth_settings.mcp_scope],
        ),
        required_scopes=[auth_settings.mcp_scope],
        resource_server_url=None,
    )

    # Create OAuth routes without built-in registration
    routes = create_auth_routes(
        provider=oauth_provider,
        issuer_url=mcp_auth_settings.issuer_url,
        service_documentation_url=mcp_auth_settings.service_documentation_url,
        client_registration_options=None,  # Disable built-in registration
        revocation_options=mcp_auth_settings.revocation_options,
    )

    # Add debug wrapper for token endpoint
    original_token_route = None
    for i, route in enumerate(routes):
        if route.path == "/token" and route.methods is not None and "POST" in route.methods:
            original_token_route = route

            # Create debug wrapper
            async def debug_token_handler(request: Request) -> Response:
                logger.info("=== TOKEN ENDPOINT DEBUG ===")
                logger.info(f"Method: {request.method}")
                logger.info(f"URL: {request.url}")
                logger.info(f"Headers: {dict(request.headers)}")

                try:
                    # Read the raw body
                    body = await request.body()
                    logger.info(f"Raw body: {body.decode()}")

                    # Check for device_code grant type
                    from urllib.parse import parse_qs

                    parsed_body = parse_qs(body.decode())
                    grant_type = parsed_body.get("grant_type", [""])[0]

                    if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
                        logger.info("=== DEVICE CODE TOKEN EXCHANGE ===")
                        return await handle_device_code_token_exchange(
                            parsed_body, oauth_provider, auth_settings
                        )

                    # Try to parse form data
                    if request.headers.get("content-type", "").startswith(
                        "application/x-www-form-urlencoded"
                    ):
                        # Reconstruct request with body

                        scope = dict(request.scope).copy()

                        async def url_encode_receive() -> dict[str, str | bytes]:
                            return {"type": "http.request", "body": body}

                        new_request = Request(scope, url_encode_receive)
                        form_data = await new_request.form()
                        logger.info(f"Form data: {dict(form_data)}")

                    # Call original handler - handle ASGI interface properly
                    logger.info("Calling original token endpoint")

                    # Create a new scope and receive callable with fresh body
                    scope = dict(request.scope).copy()

                    async def receive() -> dict[str, str | bytes | bool]:
                        return {
                            "type": "http.request",
                            "body": body,
                            "more_body": False,
                        }

                    # Create response handler
                    response_started = False
                    response_data = {"status": 500, "headers": [], "body": b""}

                    async def send(message: MutableMapping[str, Any]) -> None:
                        nonlocal response_started, response_data
                        if message["type"] == "http.response.start":
                            response_started = True
                            response_data["status"] = message["status"]
                            response_data["headers"] = message.get("headers", [])
                        elif message["type"] == "http.response.body":
                            response_data["body"] += message.get("body", b"")

                    # Call the endpoint as ASGI app
                    await original_token_route.app(scope, receive, send)  # noqa: B023

                    logger.info(f"Token endpoint result: {response_data['status']}")

                    # Log response body for debugging
                    if response_data["body"]:
                        try:
                            response_text = cast(bytes, response_data["body"]).decode("utf-8")
                            logger.info(f"Token endpoint response body: {response_text}")
                        except Exception:
                            logger.info(
                                f"Token endpoint response body (raw): {response_data['body']}"
                            )

                    # Convert headers back to dict format for Response
                    headers_dict = {}
                    for name, value in response_data["headers"]:  # type: ignore
                        headers_dict[name.decode()] = value.decode()

                    return Response(
                        content=response_data["body"],
                        status_code=cast(int, response_data["status"]),
                        headers=headers_dict,
                    )

                except Exception as e:
                    logger.error(f"Token endpoint error: {e}")
                    logger.error("Traceback: ", exc_info=True)
                    return server_error(str(e))

            # Replace the route with debug wrapper
            routes[i] = Route(route.path, debug_token_handler, methods=route.methods)
            break

    # Add OAuth callback route (GET) - receives callback from TaskManager
    async def oauth_callback_handler(request: Request) -> Response:
        """Handle OAuth callback from TaskManager."""
        return await oauth_provider.handle_oauth_callback(request)

    routes.append(Route("/oauth/callback", endpoint=oauth_callback_handler, methods=["GET"]))

    # Add MCP client callback route
    async def mcp_client_callback_handler(request: Request) -> Response:
        """Handle callback from MCP client OAuth flow."""
        from starlette.responses import HTMLResponse

        # Extract auth code and state from query params
        code = request.query_params.get("code")
        error = request.query_params.get("error")

        if error:
            return HTMLResponse(
                f"""
            <html>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """,
                status_code=400,
            )

        if code:
            return HTMLResponse(
                """
            <html>
            <body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>setTimeout(() => window.close(), 2000);</script>
            </body>
            </html>
            """
            )

        return HTMLResponse("Invalid callback", status_code=400)

    routes.append(Route("/callback", endpoint=mcp_client_callback_handler, methods=["GET"]))

    # Add token introspection endpoint (RFC 7662) for Resource Servers
    async def introspect_handler(request: Request) -> Response:
        """
        Token introspection endpoint for Resource Servers.

        Resource Servers call this endpoint to validate tokens without
        needing direct access to token storage.
        """
        form = await request.form()
        token = form.get("token")
        logger.info("=== INTROSPECT HANDLER ===")

        if isinstance(token, str):
            logger.info(
                f"Token from request: {token[:20]}...{token[-10:]}"
                if token and len(token) > 30
                else f"Token: {token}"
            )

        if not token or not isinstance(token, str):
            logger.warning("No token or invalid token type in request")
            return JSONResponse({"active": False}, status_code=400)

        # Use provider's introspection method
        introspection_result = await oauth_provider.introspect_token(token)
        logger.info(f"Introspection result: {introspection_result}")

        if not introspection_result:
            return JSONResponse({"active": False})

        return JSONResponse(introspection_result)

    routes.append(
        Route(
            "/introspect",
            endpoint=cors_middleware(introspect_handler, ["POST", "OPTIONS"]),
            methods=["POST", "OPTIONS"],
        )
    )

    # Add dynamic client registration endpoint (RFC 7591)
    async def register_handler(request: Request) -> Response:
        """
        Dynamic Client Registration endpoint (RFC 7591).

        Allows Claude Code to register itself as an OAuth client.
        """
        try:
            # Log the raw request for debugging
            body = await request.body()
            logger.warning(f"Registration request body: {body.decode()}")
            logger.warning(f"Registration request headers: {dict(request.headers)}")

            # Try to parse as JSON
            registration_data = json.loads(body) if body else {}
            logger.warning(f"Parsed registration data: {registration_data}")
        except Exception as e:
            logger.error(f"Failed to parse registration request: {e}")
            return invalid_request("Invalid JSON")

        # Set default redirect URIs if not provided
        redirect_uris = registration_data.get("redirect_uris", [])

        # If redirect URIs were provided, also add the non-debug variant
        if redirect_uris:
            # Add both /debug and non-debug variants for MCP Inspector
            additional_uris = []
            for uri in redirect_uris:
                if "/oauth/callback/debug" in uri:
                    # Add the non-debug variant
                    non_debug_uri = uri.replace("/oauth/callback/debug", "/oauth/callback")
                    if non_debug_uri not in redirect_uris:
                        additional_uris.append(non_debug_uri)
                elif "/oauth/callback" in uri and "/debug" not in uri:
                    # Add the debug variant
                    debug_uri = uri.replace("/oauth/callback", "/oauth/callback/debug")
                    if debug_uri not in redirect_uris:
                        additional_uris.append(debug_uri)
            redirect_uris.extend(additional_uris)

        if not redirect_uris:
            redirect_uris = [
                "http://localhost:3000/callback",  # Common local development
                "https://claude.ai/callback",  # Claude Web callback
            ]

        # Create OAuth client via backend API
        # Use ensure_valid_api_client() to handle token expiration
        valid_client = ensure_valid_api_client()
        if not valid_client:
            return server_error("Backend API not available")

        client_name = f"claude-code-{secrets.token_hex(4)}"

        # Create client in backend database
        # Include device_code grant for headless/CLI clients
        # Note: Public client auth method (RFC 6749 Section 2.1) is handled by backend
        api_response = valid_client.create_oauth_client(
            name=client_name,
            redirect_uris=redirect_uris,
            grant_types=["authorization_code", "refresh_token", "device_code"],
            scopes=[auth_settings.mcp_scope],
        )

        logger.info(f"API response status: {api_response.success}")
        logger.info(f"API response status_code: {api_response.status_code}")
        logger.info(f"API response data: {api_response.data}")
        logger.info(f"API response error: {api_response.error}")

        if not api_response.success:
            logger.error(f"Failed to create OAuth client: {api_response.error}")
            return server_error(f"Failed to create client: {api_response.error}")

        # Extract client credentials from API response
        client_data = api_response.data
        if client_data is None:
            logger.error("No client data returned from API - got None")
            logger.error(
                f"Full API response: success={api_response.success}, status={api_response.status_code}, error={api_response.error}"
            )
            return server_error("No client data returned from backend")

        # Validate that client_data is a dictionary before calling .get()
        if not isinstance(client_data, dict):
            logger.error(
                f"Invalid client data type from API: expected dict, got {type(client_data).__name__}. Value: {client_data!r}"
            )
            return server_error("Invalid response from backend")

        client_id = client_data.get("client_id") or client_data.get("clientId")
        client_secret = client_data.get("client_secret") or client_data.get("clientSecret")

        # Check if this is a public client (no secret required)
        is_public_client = (
            client_data.get("is_public") is True
            or client_data.get("token_endpoint_auth_method") == "none"
        )

        # Public clients don't have secrets - only require client_id
        if not client_id or (not client_secret and not is_public_client):
            logger.error(f"Invalid client data returned from API: {client_data}")
            return server_error("Invalid client data from backend")

        # Store in local cache for immediate use
        # Use the actual auth method from the API response (we create public clients for MCP)
        actual_auth_method = client_data.get("token_endpoint_auth_method") or (
            "none" if is_public_client else "client_secret_post"
        )

        client_info = {
            "client_id": client_id,
            "client_secret": client_secret if not is_public_client else None,
            "redirect_uris": redirect_uris,
            "response_types": ["code"],
            "grant_types": ["authorization_code", "refresh_token", "device_code"],
            "token_endpoint_auth_method": actual_auth_method,
            "scope": auth_settings.mcp_scope,
            "created_at": int(time.time()),
        }
        registered_clients[client_id] = client_info

        # RFC 7591 client registration response
        registration_response = {
            "client_id": client_id,
            "client_id_issued_at": int(time.time()),
            "redirect_uris": redirect_uris,
            "response_types": ["code"],
            "grant_types": ["authorization_code", "refresh_token", "device_code"],
            "token_endpoint_auth_method": actual_auth_method,
            "scope": auth_settings.mcp_scope,
        }

        # Only include client_secret for confidential clients (not public clients)
        if not is_public_client and client_secret:
            registration_response["client_secret"] = client_secret
            registration_response["client_secret_expires_at"] = 0  # Never expires

        # Log for debugging
        logger.info(f"Registered new OAuth client: {client_id}")

        return JSONResponse(registration_response, status_code=201)

    routes.append(
        Route(
            "/register",
            endpoint=cors_middleware(register_handler, ["POST", "OPTIONS"]),
            methods=["POST", "OPTIONS"],
        )
    )

    # Add device authorization endpoint (RFC 8628)
    async def device_code_handler(request: Request) -> Response:
        """
        Device Authorization endpoint (RFC 8628).

        This endpoint initiates the device authorization flow for headless clients
        that cannot open a browser. It proxies the request to TaskManager's
        device authorization endpoint.

        Security features:
        - Input validation for client_id
        - Rate limiting to prevent abuse
        - Request timeouts to prevent blocking
        - Proper error handling without information leakage
        """
        form = await request.form()
        client_id = form.get("client_id")
        scope = form.get("scope")

        logger.debug(f"Device code request from client: {client_id}")

        # === Input Validation ===
        if not client_id:
            return invalid_request("client_id is required")

        client_id_str = str(client_id)

        # Validate client_id format to prevent injection attacks
        if not VALID_ID_PATTERN.match(client_id_str):
            logger.warning("Invalid client_id format in device code request")
            return invalid_request("Invalid client_id format")

        # === Rate Limiting ===
        if not device_code_limiter.is_allowed(client_id_str):
            retry_after = device_code_limiter.get_retry_after(client_id_str)
            logger.warning(
                f"Rate limit exceeded for device code request from client: {client_id_str}"
            )
            return rate_limit_exceeded("Too many device code requests", retry_after)

        # === Proxy request to TaskManager with timeout ===
        timeout = aiohttp.ClientTimeout(total=TokenConfig.HTTP_REQUEST_TIMEOUT_SECONDS)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                device_data: dict[str, str] = {"client_id": client_id_str}
                if scope:
                    device_data["scope"] = str(scope)

                device_url = f"{auth_settings.base_url}/api/oauth/device/code"
                logger.debug("Proxying device code request to TaskManager")

                async with session.post(device_url, data=device_data) as resp:
                    # Handle non-JSON responses gracefully
                    try:
                        response_data = await resp.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as e:
                        logger.error(f"Invalid JSON response from TaskManager device endpoint: {e}")
                        return backend_invalid_response()

                    # Validate response is a dict
                    if not isinstance(response_data, dict):
                        logger.error(
                            f"Unexpected response type from TaskManager: {type(response_data)}"
                        )
                        return backend_invalid_response()

                    if resp.status != 200:
                        logger.warning(f"Device code request failed with status: {resp.status}")
                        return JSONResponse(
                            response_data,
                            status_code=resp.status,
                            headers={"Cache-Control": "no-store"},
                        )

                    # Return the device code response
                    # The verification_uri points to TaskManager where user will authenticate
                    logger.info(f"Device code issued for client: {client_id_str}")
                    return JSONResponse(
                        response_data,
                        status_code=200,
                        headers={"Cache-Control": "no-store"},
                    )

        except TimeoutError:
            logger.error("Timeout connecting to TaskManager for device code request")
            return backend_timeout()
        except aiohttp.ClientError as e:
            logger.error(f"Connection error to TaskManager: {e}")
            return backend_connection_error()

    routes.append(
        Route(
            "/device/code",
            endpoint=cors_middleware(device_code_handler, ["POST", "OPTIONS"]),
            methods=["POST", "OPTIONS"],
        )
    )

    # Add custom OAuth metadata endpoint to advertise registration support
    async def oauth_metadata_handler(request: Request) -> JSONResponse:
        """OAuth 2.0 Authorization Server Metadata with registration endpoint"""
        server_url_str = str(server_url).rstrip("/")

        return JSONResponse(
            {
                "issuer": server_url_str,
                "authorization_endpoint": f"{server_url_str}/authorize",
                "token_endpoint": f"{server_url_str}/token",
                "registration_endpoint": f"{server_url_str}/register",  # Advertise registration
                "introspection_endpoint": f"{server_url_str}/introspect",
                "device_authorization_endpoint": f"{server_url_str}/device/code",  # RFC 8628
                "response_types_supported": ["code"],
                "grant_types_supported": [
                    "authorization_code",
                    "refresh_token",
                    "urn:ietf:params:oauth:grant-type:device_code",
                ],
                "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
                "code_challenge_methods_supported": ["S256"],
                "scopes_supported": [auth_settings.mcp_scope],
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    # Add OAuth metadata routes - insert at beginning to override MCP defaults
    routes.insert(
        0,
        Route(
            "/.well-known/oauth-authorization-server",
            endpoint=cors_middleware(oauth_metadata_handler, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        ),
    )

    routes.insert(
        1,
        Route(
            "/.well-known/openid-configuration",
            endpoint=cors_middleware(oauth_metadata_handler, ["GET", "OPTIONS"]),
            methods=["GET", "OPTIONS"],
        ),
    )

    # Add logging middleware
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        logger.info("=== Incoming Request to Auth Server ===")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Path: {request.url.path}")
        logger.info(f"Host header: {request.headers.get('host')}")
        logger.info(f"X-Forwarded-Proto: {request.headers.get('x-forwarded-proto')}")
        logger.info(f"X-Forwarded-For: {request.headers.get('x-forwarded-for')}")
        logger.info(f"User-Agent: {request.headers.get('user-agent')}")

        response = await call_next(request)

        logger.info(f"Response status: {response.status_code}")
        return response

    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware

    class LoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(
            self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            return await log_requests(request, call_next)

    return Starlette(routes=routes, middleware=[Middleware(LoggingMiddleware)])


async def run_server(
    host: str, port: int, server_url: AnyHttpUrl, auth_settings: TaskManagerAuthSettings
) -> None:
    """Run the Authorization Server."""
    # Initialize persistent token storage if DATABASE_URL is configured
    token_storage: TokenStorage | None = None
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        logger.info("Initializing database token storage...")
        token_storage = TokenStorage(database_url)
        try:
            await token_storage.initialize()
            logger.info("Database token storage initialized successfully")

            # Clean up any expired tokens on startup
            cleaned = await token_storage.cleanup_expired_tokens()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired tokens on startup")
        except Exception as e:
            logger.error(f"Failed to initialize database token storage: {e}")
            logger.warning("Falling back to in-memory token storage")
            token_storage = None
    else:
        logger.warning(
            "DATABASE_URL not configured - using in-memory token storage. "
            "Tokens will be lost on server restart!"
        )

    auth_server = create_authorization_server(
        host, port, server_url, auth_settings, token_storage=token_storage
    )

    config = Config(
        auth_server,
        host=host,
        port=port,
        log_level="info",
    )
    server = Server(config)

    # Remove trailing slash from server_url if present (required for OAuth spec)
    server_url_str = str(server_url).rstrip("/")
    server_url = AnyHttpUrl(server_url_str)

    storage_type = "database" if token_storage else "in-memory"
    logger.info("=" * 60)
    logger.info(f"🚀 MCP Authorization Server running on {server_url}")
    logger.info(f"📍 Public URL: {server_url}")
    logger.info(f"🔌 Binding to: {host}:{port}")
    logger.info(f"💾 Token storage: {storage_type}")
    logger.info("=" * 60)

    try:
        await server.serve()
    finally:
        # Clean up token storage on shutdown
        if token_storage:
            await token_storage.close()


@click.command()
@click.option("--port", default=9000, help="Port to listen on")
@click.option("--taskmanager-url", default="localhost:4321", help="TaskManager base URL")
@click.option(
    "--server-url",
    help="Auth server URL (for redirect URIs). Defaults to http://localhost:PORT",
)
# @click.option("--client-id", help="OAuth client ID (if already registered)")
# @click.option("--client-secret", help="OAuth client secret (if already registered)")
def main(port: int, taskmanager_url: str, server_url: str | None = None) -> int:
    """
    Run the MCP Authorization Server with TaskManager OAuth integration.

    This server handles OAuth flows by delegating authentication to your
    existing TaskManager OAuth endpoints.
    """
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get OAuth client credentials for OAuth flow and API access
    oauth_client_id = os.environ["TASKMANAGER_CLIENT_ID"]
    oauth_client_secret = os.environ["TASKMANAGER_CLIENT_SECRET"]

    # Initialize API client for backend database operations using OAuth2 Client Credentials
    # This is the recommended approach for server-to-server authentication as it:
    # 1. Uses stateless Bearer tokens instead of session cookies
    # 2. Doesn't require separate user credentials
    # 3. Tokens can be refreshed by simply re-authenticating with client credentials
    global api_client, _api_credentials
    from taskmanager_sdk import create_client_credentials_client

    # Store credentials for automatic re-authentication when token expires
    base_url = f"{taskmanager_url}/api"
    _api_credentials = {
        "client_id": oauth_client_id,
        "client_secret": oauth_client_secret,
        "base_url": base_url,
    }

    try:
        logger.info("Authenticating with backend API using client credentials...")
        api_client = create_client_credentials_client(
            oauth_client_id, oauth_client_secret, base_url
        )
        logger.info("API client authenticated successfully using OAuth2 Client Credentials")
    except AuthenticationError as e:
        logger.error(f"Failed to authenticate with backend API: {e}")
        logger.error("Ensure the OAuth client has 'client_credentials' in its grant_types")
        return 1

    # Verify the API client can make authenticated requests
    logger.info("Verifying API client can access protected endpoints...")
    test_response = api_client.get_oauth_clients()
    if test_response.success:
        logger.info("API client verified - able to access protected endpoints")
    else:
        logger.warning(f"API client verification failed: {test_response.error}")
        logger.warning("Will attempt to continue, but API calls may not work properly")

    # Load TaskManager auth settings with OAuth client credentials
    auth_settings = TaskManagerAuthSettings(
        base_url=taskmanager_url,
        client_id=oauth_client_id,
        client_secret=oauth_client_secret,
    )

    # Bind address configurable via environment, defaults to all interfaces for Docker
    host = os.getenv("MCP_AUTH_HOST", "0.0.0.0")  # nosec B104

    # Use environment variable for public server URL, or default to localhost
    if server_url is None:
        server_url = os.getenv("MCP_AUTH_SERVER_URL", f"http://localhost:{port}")
    """
    server_settings = AuthServerSettings(
        host=host,
        port=port,
        server_url=AnyHttpUrl(server_url),
        auth_callback_path=f"{server_url}/oauth/callback",
    )
    """

    logger.info(f"TaskManager URL: {taskmanager_url}")

    asyncio.run(run_server(host, port, AnyHttpUrl(server_url), auth_settings))
    return 0


if __name__ == "__main__":
    main()
