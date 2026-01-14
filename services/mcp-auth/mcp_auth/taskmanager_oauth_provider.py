"""
TaskManager OAuth Provider for MCP Server

This provider integrates with the existing OAuth endpoints in the taskmanager application
to provide authentication for MCP (Model Context Protocol) servers.

OAuth 2.0 Flow Overview:
1. Authorization Request: Client redirects user to /oauth/authorize
2. User Login: User authenticates with taskmanager credentials
3. Authorization Grant: User consents, server creates authorization code
4. Access Token Request: Client exchanges code for access token at /oauth/token
5. Resource Access: Client uses access token to access protected MCP resources

This implementation handles the MCP-specific parts of the OAuth flow while
delegating the actual OAuth logic to your existing taskmanager endpoints.
"""

import logging
import os
import secrets
import time
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlencode

import aiohttp
from dotenv import load_dotenv
from mcp.server.auth.provider import (
    AccessToken,
    AccessTokenT,
    AuthorizationCode,
    AuthorizationCodeT,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RefreshTokenT,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from taskmanager_sdk import TokenConfig

if TYPE_CHECKING:
    from .token_storage import TokenStorage

logger = logging.getLogger(__name__)


load_dotenv()
OAUTH_PROVIDER = os.environ["TASKMANAGER_OAUTH_HOST"]
MCP_SERVER = os.environ["MCP_SERVER"]


class TaskManagerAuthSettings(BaseSettings):
    """
    Settings for TaskManager OAuth integration.

    These settings configure how the MCP server connects to your taskmanager
    OAuth endpoints for authentication.
    """

    model_config = SettingsConfigDict(env_prefix="TASKMANAGER_")

    # TaskManager OAuth endpoints
    base_url: str = "http://localhost:4321"
    authorize_endpoint: str = "/api/oauth/authorize"
    token_endpoint: str = "/api/oauth/token"
    clients_endpoint: str = "/api/oauth/clients"

    # OAuth client credentials (will be auto-registered if not provided)
    client_id: str | None = None
    client_secret: str | None = None
    client_name: str = "MCP Server"

    # MCP-specific settings
    mcp_scope: str = "read"  # Default scope for MCP access

    # Session settings for admin operations (if needed)
    admin_session_cookie: str | None = None  # For auto-registering clients


class TaskManagerOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCodeT, RefreshTokenT, AccessTokenT]
):
    """
    OAuth provider that integrates with TaskManager's existing OAuth endpoints.

    This provider acts as a bridge between the MCP server authentication system
    and your existing taskmanager OAuth implementation. It handles:

    1. Client registration with taskmanager
    2. OAuth authorization flow delegation
    3. Token exchange and validation
    4. User information retrieval

    The actual OAuth logic is handled by your taskmanager endpoints, while this
    provider manages the MCP-specific integration details.
    """

    def __init__(
        self,
        settings: TaskManagerAuthSettings,
        server_url: str,
        token_storage: "TokenStorage | None" = None,
    ):
        """
        Initialize the TaskManager OAuth provider.

        Args:
            settings: Configuration for connecting to taskmanager
            server_url: The URL of this MCP server (for redirect URIs)
            token_storage: Optional persistent token storage. If not provided,
                          tokens are stored in memory (not recommended for production).
        """
        self.settings = settings
        self.server_url = server_url
        self.token_storage = token_storage

        # In-memory storage (used as fallback or for auth codes/state)
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}  # Fallback if no token_storage
        self.refresh_tokens: dict[str, RefreshToken] = {}  # In-memory refresh tokens
        self.refresh_token_resources: dict[
            str, str | None
        ] = {}  # Resource binding for refresh tokens
        self.state_mapping: dict[str, dict[str, str | None]] = {}
        self.registered_clients: dict[str, Any] = {}

        # HTTP session for making requests to taskmanager
        self._session: aiohttp.ClientSession | None = None

        storage_type = "database" if token_storage else "in-memory"
        logger.info(
            f"Initialized TaskManager OAuth provider for {settings.base_url} "
            f"with {storage_type} token storage"
        )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for taskmanager API calls."""
        if self._session is None:
            # Create session with headers that bypass CSRF for API calls
            headers = {
                "X-Requested-With": "XMLHttpRequest",  # Often bypasses CSRF
                "Accept": "application/json",
            }
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        """Clean up HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """
        Get OAuth client information.

        This first checks our local cache, then attempts to retrieve from
        taskmanager if not found locally.
        """
        logger.info("=== GET CLIENT ===")
        logger.info(f"Looking for client: {client_id}")
        logger.info(f"Local cache clients: {list(self.clients.keys())}")

        # Check local cache first
        if client_id in self.clients:
            cached_client = self.clients[client_id]
            logger.info(f"Found client {client_id} in local cache")
            logger.info(f"Cached client auth method: {cached_client.token_endpoint_auth_method}")
            return cached_client

        # Check registered clients from auth server
        if self.registered_clients:
            logger.info(f"Registered clients: {list(self.registered_clients.keys())}")
            if client_id in self.registered_clients:
                client_data = self.registered_clients[client_id]
                logger.info(f"Found client {client_id} in registered clients: {client_data}")

                # Convert to OAuthClientInformationFull format
                logger.info(
                    f"Creating OAuthClientInformationFull with auth_method: {client_data['token_endpoint_auth_method']}"
                )

                # For "none" auth method, don't provide client_secret
                client_secret = (
                    None
                    if client_data["token_endpoint_auth_method"] == "none"
                    else client_data["client_secret"]
                )

                client_info = OAuthClientInformationFull(
                    client_id=client_data["client_id"],
                    client_secret=client_secret,
                    redirect_uris=client_data["redirect_uris"],
                    response_types=client_data["response_types"],
                    grant_types=client_data["grant_types"],
                    token_endpoint_auth_method=client_data["token_endpoint_auth_method"],
                    scope=client_data["scope"],
                )
                # Cache it locally for future use
                self.clients[client_id] = client_info
                logger.info(f"Successfully converted and cached client {client_id}")
                logger.info(f"Final client auth method: {client_info.token_endpoint_auth_method}")
                return client_info
        else:
            logger.warning("No registered_clients attribute found on provider")

        # TODO: Add endpoint to taskmanager to retrieve client info by ID
        # For now, return None if not found locally
        logger.error(f"Client {client_id} not found in local cache or registered clients")
        return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """
        Register a new OAuth client.

        This stores the client information locally and optionally registers
        it with the taskmanager system if admin credentials are available.
        """
        if client_info.client_id is None:
            raise ValueError("client_id is required for OAuth client registration")
        self.clients[client_info.client_id] = client_info
        logger.info(f"Registered OAuth client: {client_info.client_id}")

        # TODO: Optionally register with taskmanager if admin session available
        if self.settings.admin_session_cookie:
            await self._register_with_taskmanager(client_info)

    async def _register_with_taskmanager(self, client_info: OAuthClientInformationFull) -> None:
        """
        Register client with taskmanager (requires admin session).

        This is a stub for automatically registering MCP clients with your
        taskmanager system. You'll need to implement the admin authentication
        part based on your needs.
        """
        # TODO: Implement client registration with taskmanager
        # This would POST to /api/oauth/clients with admin credentials
        logger.info("Auto-registration with taskmanager not yet implemented")
        pass

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """
        Generate authorization URL that redirects to taskmanager's OAuth flow.

        This creates the authorization URL that will redirect users to your
        taskmanager's OAuth consent page. The user will authenticate there
        and then be redirected back to complete the MCP authentication.
        """
        state = params.state or secrets.token_hex(16)

        # Store state mapping for callback processing
        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": str(params.redirect_uri_provided_explicitly),
            "client_id": client.client_id,
            "resource": params.resource,  # RFC 8707 resource parameter
        }

        # Build authorization URL pointing to taskmanager
        # IMPORTANT: Use the TaskManager OAuth client ID (this auth server's credentials),
        # NOT the MCP client's ID. The MCP client ID is only used for MCP token issuance.
        auth_params = {
            "client_id": self.settings.client_id,  # Use TaskManager OAuth client ID
            "redirect_uri": f"{self.server_url.rstrip('/')}/oauth/callback",  # This server handles callback
            "response_type": "code",
            "scope": self.settings.mcp_scope,
            "state": state,
        }

        # Note: We intentionally do NOT forward PKCE parameters to TaskManager
        # because we're acting as a proxy. The MCP client's PKCE verification
        # will be handled by the MCP auth server directly.

        auth_url = (
            f"{self.settings.base_url}{self.settings.authorize_endpoint}?{urlencode(auth_params)}"
        )

        logger.info(f"Generated authorization URL: {auth_url}")
        logger.info(f"Using TaskManager client_id: {self.settings.client_id}")
        logger.info(f"MCP client_id (for later token issuance): {client.client_id}")
        return auth_url

    async def handle_oauth_callback(self, request: Request) -> Response:
        """
        Handle OAuth callback from taskmanager.

        This processes the authorization code received from taskmanager's
        OAuth flow and exchanges it for an access token, then creates
        an MCP authorization code for the original client.
        """
        # Get parameters from callback
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error:
            logger.error(f"OAuth callback error: {error}")
            raise HTTPException(400, f"OAuth error: {error}")

        if not code or not state:
            logger.error("Missing code or state in OAuth callback")
            raise HTTPException(400, "Missing code or state parameter")

        # Retrieve state mapping
        state_data = self.state_mapping.get(state)
        if not state_data:
            logger.error(f"Invalid state parameter: {state}")
            raise HTTPException(400, "Invalid state parameter")

        try:
            # Exchange authorization code with taskmanager for access token
            access_token = await self._exchange_code_with_taskmanager(code, state)

            # Create MCP authorization code for the original client
            mcp_code = f"mcp_{secrets.token_hex(16)}"
            auth_code = AuthorizationCode(
                code=mcp_code,
                client_id=state_data["client_id"] or "",
                redirect_uri=AnyHttpUrl(state_data["redirect_uri"] or ""),
                redirect_uri_provided_explicitly=state_data["redirect_uri_provided_explicitly"]
                == "True",
                expires_at=time.time() + TokenConfig.AUTHORIZATION_CODE_TTL_SECONDS,
                scopes=[self.settings.mcp_scope],
                code_challenge=state_data["code_challenge"] or "",
                resource=state_data.get("resource"),
            )
            self.auth_codes[mcp_code] = auth_code

            # Store the taskmanager access token for later use
            # TODO: You might want to validate/introspect the token here
            self.tokens[f"tm_{access_token}"] = AccessToken(
                token=f"tm_{access_token}",
                client_id=state_data["client_id"] or "",
                scopes=[self.settings.mcp_scope],
                expires_at=int(time.time()) + TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS,
                resource=state_data.get("resource"),
            )

            # Clean up state
            del self.state_mapping[state]

            # Redirect back to original client
            redirect_uri = construct_redirect_uri(
                state_data["redirect_uri"] or "", code=mcp_code, state=state
            )
            return RedirectResponse(url=redirect_uri, status_code=302)

        except Exception as e:
            logger.error(f"Error handling OAuth callback: {e}")
            raise HTTPException(500, "Internal server error during OAuth callback") from e

    async def _exchange_code_with_taskmanager(self, code: str, state: str) -> str:
        """
        Exchange authorization code with taskmanager for access token.

        This makes a request to your taskmanager's token endpoint to
        exchange the authorization code for an access token.

        IMPORTANT: This uses the TaskManager OAuth client credentials (this auth server's
        credentials), NOT the MCP client's credentials. The authorization code was issued
        to the TaskManager OAuth client, so we must use those credentials to exchange it.
        """
        session = await self._get_session()

        # Use TaskManager OAuth client credentials for the token exchange
        # The authorization code was issued to this client ID, not the MCP client
        client_id = self.settings.client_id
        client_secret = self.settings.client_secret

        if not client_id or not client_secret:
            logger.error("TaskManager OAuth credentials not configured!")
            raise HTTPException(
                500, "Server configuration error: TaskManager OAuth credentials missing"
            )

        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": f"{self.server_url.rstrip('/')}/oauth/callback",
        }

        token_url = f"{self.settings.base_url}{self.settings.token_endpoint}"

        logger.info(f"Exchanging token at {token_url}")
        logger.info(f"Using TaskManager client_id: {client_id}")
        logger.debug(
            "Using redirect_uri for token exchange"
        )  # Avoid logging redirect URI directly, as best practice.

        async with session.post(token_url, data=token_data) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"Token exchange failed: {response.status} - {error_text}")
                logger.error(f"Request data (client_id): {client_id}")
                raise HTTPException(400, f"Token exchange failed: {response.status}")

            token_response = await response.json()
            logger.info(f"Token response from TaskManager: {token_response}")
            access_token = token_response.get("access_token")

            if not access_token:
                logger.error(f"No access token in response. Full response: {token_response}")
                raise HTTPException(400, "No access token received")

            logger.info("Successfully exchanged code for access token")
            return str(access_token)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCodeT | None:
        """Load an authorization code from storage."""
        logger.info("=== LOADING AUTH CODE ===")
        logger.info(f"Requested code: {authorization_code}")
        logger.info(f"Client: {client.client_id}")
        logger.info(f"Available auth codes: {list(self.auth_codes.keys())}")

        auth_code = self.auth_codes.get(authorization_code)
        if auth_code:
            logger.info(f"Found auth code for client: {auth_code.client_id}")
            logger.info(f"Auth code expires at: {auth_code.expires_at}")
            logger.info(f"Auth code scopes: {auth_code.scopes}")
            logger.info(f"Auth code redirect URI: {auth_code.redirect_uri}")
        else:
            logger.error(f"Auth code not found: {authorization_code}")
            logger.error("This suggests the OAuth callback flow never completed properly")
        return cast(AuthorizationCodeT, auth_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """
        Exchange MCP authorization code for MCP access token and refresh token.

        This creates the final MCP access token that will be used by
        the MCP client to access protected resources, along with a refresh
        token for obtaining new access tokens without re-authentication.
        """
        logger.info("=== EXCHANGING AUTH CODE ===")
        logger.info(f"Auth code: {authorization_code.code}")
        logger.info(f"Client: {client.client_id}")
        logger.info(f"Code challenge: {authorization_code.code_challenge}")
        logger.info(f"Scopes: {authorization_code.scopes}")
        logger.info(f"Redirect URI: {authorization_code.redirect_uri}")

        if authorization_code.code not in self.auth_codes:
            logger.error(f"Authorization code {authorization_code.code} not found in auth_codes")
            logger.error(f"Available codes: {list(self.auth_codes.keys())}")
            raise ValueError("Invalid authorization code")

        # Generate MCP access token
        mcp_token = f"mcp_{secrets.token_hex(32)}"
        logger.info(f"Generated MCP token: {mcp_token}")

        # Generate MCP refresh token
        mcp_refresh_token = f"mcp_rt_{secrets.token_hex(32)}"
        refresh_expires_at = int(time.time()) + TokenConfig.MCP_REFRESH_TOKEN_TTL_SECONDS
        logger.info(f"Generated MCP refresh token: {mcp_refresh_token[:20]}...")

        # Store MCP token (linked to taskmanager token if needed)
        if client.client_id is None:
            raise ValueError("client_id is required for token exchange")
        expires_at = int(time.time()) + TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS
        access_token = AccessToken(
            token=mcp_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=expires_at,
            resource=authorization_code.resource,
        )

        # Store in database if available, otherwise fall back to in-memory
        if self.token_storage:
            await self.token_storage.store_token(
                token=mcp_token,
                client_id=client.client_id,
                scopes=authorization_code.scopes,
                expires_at=expires_at,
                resource=authorization_code.resource,
            )
            await self.token_storage.store_refresh_token(
                refresh_token=mcp_refresh_token,
                client_id=client.client_id,
                scopes=authorization_code.scopes,
                expires_at=refresh_expires_at,
                resource=authorization_code.resource,
            )
            token_count = await self.token_storage.get_token_count()
            logger.info(
                f"Stored access and refresh tokens in database, total access tokens: {token_count}"
            )
        else:
            self.tokens[mcp_token] = access_token
            self.refresh_tokens[mcp_refresh_token] = RefreshToken(
                token=mcp_refresh_token,
                client_id=client.client_id,
                scopes=authorization_code.scopes,
                expires_at=refresh_expires_at,
            )
            self.refresh_token_resources[mcp_refresh_token] = authorization_code.resource
            logger.info(
                f"Stored access and refresh tokens in memory, total access tokens: {len(self.tokens)}"
            )

        # Clean up authorization code
        del self.auth_codes[authorization_code.code]
        logger.info(f"Cleaned up auth code, remaining codes: {len(self.auth_codes)}")

        oauth_token = OAuthToken(
            access_token=mcp_token,
            token_type="Bearer",  # nosec B106 - OAuth token type, not a password
            expires_in=TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(authorization_code.scopes),
            refresh_token=mcp_refresh_token,
        )

        return oauth_token

    async def load_access_token(self, token: str) -> AccessTokenT | None:
        """
        Load and validate an access token.

        This checks if the token exists and hasn't expired. For tokens
        that were issued based on taskmanager authentication, you might
        want to add additional validation here.
        """
        logger.info("=== LOAD ACCESS TOKEN ===")
        logger.info(
            f"Looking for token: {token[:20]}...{token[-10:]}"
            if len(token) > 30
            else f"Token: {token}"
        )

        # Try database storage first if available
        if self.token_storage:
            token_count = await self.token_storage.get_token_count()
            logger.info(f"Database token storage has {token_count} tokens")

            token_data = await self.token_storage.load_token(token)
            if not token_data:
                logger.warning("Token NOT FOUND in database!")
                return None

            logger.info(
                f"Token found in database! Client: {token_data['client_id']}, "
                f"Scopes: {token_data['scopes']}"
            )

            # Allow access_token to be None for later in the function
            access_token: AccessToken | None = AccessToken(
                token=token_data["token"],
                client_id=token_data["client_id"],
                scopes=token_data["scopes"],
                expires_at=token_data["expires_at"],
                resource=token_data["resource"],
            )

            logger.info(f"Token valid, expires at: {access_token.expires_at}")
            return cast(AccessTokenT, access_token)

        # Fall back to in-memory storage
        logger.info(f"In-memory token storage has {len(self.tokens)} tokens")

        access_token = self.tokens.get(token)
        if not access_token:
            logger.warning("Token NOT FOUND in memory storage!")
            logger.warning(f"Available token prefixes: {[k[:20] for k in self.tokens]}")
            return None

        logger.info(f"Token found! Client: {access_token.client_id}, Scopes: {access_token.scopes}")

        # Check if expired
        if access_token.expires_at and access_token.expires_at < time.time():
            logger.warning(
                f"Token expired at {access_token.expires_at}, current time: {time.time()}"
            )
            del self.tokens[token]
            return None

        logger.info(f"Token valid, expires at: {access_token.expires_at}")
        return cast(AccessTokenT, access_token)

    async def _get_refresh_token_resource(self, refresh_token: str) -> str | None:
        """
        Get the resource binding for a refresh token.

        Args:
            refresh_token: The refresh token string

        Returns:
            Resource string if bound, None otherwise
        """
        if self.token_storage:
            token_data = await self.token_storage.load_refresh_token(refresh_token)
            return token_data["resource"] if token_data else None
        return self.refresh_token_resources.get(refresh_token)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshTokenT | None:
        """
        Load and validate a refresh token.

        Args:
            client: The OAuth client making the request
            refresh_token: The refresh token string to validate

        Returns:
            RefreshToken if valid, None otherwise
        """
        logger.info("=== LOAD REFRESH TOKEN ===")
        logger.info(
            f"Looking for refresh token: {refresh_token[:20]}..."
            if len(refresh_token) > 20
            else f"Token: {refresh_token}"
        )
        logger.info(f"Client: {client.client_id}")

        # Try database storage first if available
        if self.token_storage:
            token_data = await self.token_storage.load_refresh_token(refresh_token)
            if not token_data:
                logger.warning("Refresh token NOT FOUND in database!")
                return None

            # Verify the token belongs to the requesting client
            if token_data["client_id"] != client.client_id:
                logger.warning(
                    f"Refresh token client mismatch: token belongs to {token_data['client_id']}, "
                    f"but request from {client.client_id}"
                )
                return None

            logger.info(f"Refresh token found in database for client: {token_data['client_id']}")

            refresh_token_obj = RefreshToken(
                token=token_data["token"],
                client_id=token_data["client_id"],
                scopes=token_data["scopes"],
                expires_at=token_data["expires_at"],
            )
            return cast(RefreshTokenT, refresh_token_obj)

        # Fall back to in-memory storage
        logger.info(f"In-memory refresh token storage has {len(self.refresh_tokens)} tokens")

        stored_token = self.refresh_tokens.get(refresh_token)
        if not stored_token:
            logger.warning("Refresh token NOT FOUND in memory storage!")
            return None

        # Verify the token belongs to the requesting client
        if stored_token.client_id != client.client_id:
            logger.warning(
                f"Refresh token client mismatch: token belongs to {stored_token.client_id}, "
                f"but request from {client.client_id}"
            )
            return None

        # Check if expired
        if stored_token.expires_at and stored_token.expires_at < time.time():
            logger.warning(f"Refresh token expired at {stored_token.expires_at}")
            del self.refresh_tokens[refresh_token]
            if refresh_token in self.refresh_token_resources:
                del self.refresh_token_resources[refresh_token]
            return None

        logger.info(f"Refresh token valid, expires at: {stored_token.expires_at}")
        return cast(RefreshTokenT, stored_token)

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """
        Exchange a refresh token for a new access token and refresh token.

        This implements refresh token rotation - the old refresh token is
        invalidated and a new one is issued for security.

        Args:
            client: The OAuth client making the request
            refresh_token: The refresh token to exchange
            scopes: Requested scopes (must be subset of original scopes)

        Returns:
            OAuthToken with new access_token and refresh_token
        """
        logger.info("=== EXCHANGE REFRESH TOKEN ===")
        logger.info(f"Client: {client.client_id}")
        logger.info(f"Refresh token: {refresh_token.token[:20]}...")
        logger.info(f"Requested scopes: {scopes}")
        logger.info(f"Original scopes: {refresh_token.scopes}")

        if client.client_id is None:
            raise ValueError("client_id is required for refresh token exchange")

        # Get the resource binding for the old refresh token
        resource = await self._get_refresh_token_resource(refresh_token.token)

        # Validate requested scopes are a subset of the original scopes
        original_scopes = set(refresh_token.scopes)
        requested_scopes = set(scopes) if scopes else original_scopes
        if not requested_scopes.issubset(original_scopes):
            logger.error(f"Requested scopes {requested_scopes} not subset of {original_scopes}")
            raise ValueError("Requested scopes exceed original grant")

        # Use the requested scopes, or fall back to original scopes
        final_scopes = list(requested_scopes) if scopes else refresh_token.scopes

        # Generate new access token
        new_access_token = f"mcp_{secrets.token_hex(32)}"
        access_expires_at = int(time.time()) + TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS

        # Generate new refresh token (token rotation for security)
        new_refresh_token = f"mcp_rt_{secrets.token_hex(32)}"
        refresh_expires_at = int(time.time()) + TokenConfig.MCP_REFRESH_TOKEN_TTL_SECONDS

        logger.info(f"Generated new access token: {new_access_token[:20]}...")
        logger.info(f"Generated new refresh token: {new_refresh_token[:20]}...")

        # Store new tokens and invalidate old refresh token
        if self.token_storage:
            # Store new access token
            await self.token_storage.store_token(
                token=new_access_token,
                client_id=client.client_id,
                scopes=final_scopes,
                expires_at=access_expires_at,
                resource=resource,
            )
            # Store new refresh token
            await self.token_storage.store_refresh_token(
                refresh_token=new_refresh_token,
                client_id=client.client_id,
                scopes=final_scopes,
                expires_at=refresh_expires_at,
                resource=resource,
            )
            # Delete old refresh token (rotation)
            await self.token_storage.delete_refresh_token(refresh_token.token)
            logger.info("Stored new tokens in database, rotated old refresh token")
        else:
            # In-memory storage
            self.tokens[new_access_token] = AccessToken(
                token=new_access_token,
                client_id=client.client_id,
                scopes=final_scopes,
                expires_at=access_expires_at,
                resource=resource,
            )
            self.refresh_tokens[new_refresh_token] = RefreshToken(
                token=new_refresh_token,
                client_id=client.client_id,
                scopes=final_scopes,
                expires_at=refresh_expires_at,
            )
            self.refresh_token_resources[new_refresh_token] = resource
            # Delete old refresh token (rotation)
            if refresh_token.token in self.refresh_tokens:
                del self.refresh_tokens[refresh_token.token]
            if refresh_token.token in self.refresh_token_resources:
                del self.refresh_token_resources[refresh_token.token]
            logger.info("Stored new tokens in memory, rotated old refresh token")

        oauth_token = OAuthToken(
            access_token=new_access_token,
            token_type="Bearer",  # nosec B106 - OAuth token type, not a password
            expires_in=TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS,
            scope=" ".join(final_scopes),
            refresh_token=new_refresh_token,
        )

        logger.info(f"Refresh token exchange complete for client: {client.client_id}")
        return oauth_token

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        """
        Revoke a token.

        This removes the token from storage. You might also want to
        notify the taskmanager system about token revocation.
        """
        token_str = str(token.token) if hasattr(token, "token") else str(token)

        if self.token_storage:
            await self.token_storage.delete_token(token_str)
            logger.info(f"Revoked token from database: {token_str[:10]}...")
        elif token_str in self.tokens:
            del self.tokens[token_str]
            logger.info(f"Revoked token from memory: {token_str[:10]}...")

    async def introspect_token(self, token: str) -> dict[str, Any] | None:
        """
        Introspect a token for Resource Server validation.

        This is used by MCP Resource Servers to validate tokens without
        direct access to token storage. Returns token metadata if valid.
        """
        logger.info("=== INTROSPECT TOKEN ===")
        logger.info(
            f"Token to introspect: {token[:20]}...{token[-10:]}"
            if len(token) > 30
            else f"Token: {token}"
        )

        if self.token_storage:
            token_count = await self.token_storage.get_token_count()
            logger.info(f"Using database storage with {token_count} tokens")
        else:
            logger.info(f"Using in-memory storage with {len(self.tokens)} tokens")
            logger.info(f"Available token keys: {[k[:20] + '...' for k in self.tokens]}")

        access_token = await self.load_access_token(token)
        if not access_token:
            logger.warning("Token not found or expired in introspection")
            return {"active": False}

        return {
            "active": True,
            "client_id": access_token.client_id,
            "scope": " ".join(access_token.scopes),
            "exp": access_token.expires_at,
            "iat": int(time.time()),
            "token_type": "Bearer",
            "aud": access_token.resource,  # RFC 8707 audience claim
        }


# Helper function to create provider instance
def create_taskmanager_oauth_provider(
    taskmanager_base_url: str = OAUTH_PROVIDER,
    server_url: str = MCP_SERVER,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> TaskManagerOAuthProvider[AuthorizationCode, RefreshToken, AccessToken]:
    """
    Convenience function to create a TaskManager OAuth provider.

    Args:
        taskmanager_base_url: Base URL of your taskmanager application
        server_url: URL of this MCP server
        client_id: OAuth client ID (if already registered)
        client_secret: OAuth client secret (if already registered)

    Returns:
        Configured TaskManagerOAuthProvider instance
    """
    settings = TaskManagerAuthSettings(
        base_url=taskmanager_base_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    return TaskManagerOAuthProvider(settings, server_url)
