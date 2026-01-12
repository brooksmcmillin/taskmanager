import datetime
import json
import logging
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse
from taskmanager_sdk import ApiResponse, TaskManagerClient

from .token_verifier import IntrospectionTokenVerifier

logger = logging.getLogger(__name__)


def validate_list_response(
    response: ApiResponse, context: str, key: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """Validate that an API response contains a list of dictionaries.

    Args:
        response: The API response to validate
        context: Description of what we're fetching (e.g., "projects", "tasks")
        key: Optional key to extract list from wrapped response (e.g., "tasks" for {"tasks": [...]})

    Returns:
        Tuple of (validated list, error message or None)
    """
    if not response.success:
        return [], response.error or f"Failed to fetch {context}"

    data = response.data
    if data is None:
        return [], None  # Empty result, not an error

    # Handle wrapped responses like {"tasks": [...]} or {"categories": [...]}
    if isinstance(data, dict):
        # Try the provided key first, then the context as a key
        for k in [key, context, f"{context}s"]:
            if k and k in data:
                data = data[k]
                break
        else:
            # No matching key found - maybe it's a different structure
            error_msg = (
                f"Backend returned {context} as dict without expected key: {list(data.keys())}"
            )
            logger.error(error_msg)
            return [], error_msg

    if not isinstance(data, list):
        error_msg = (
            f"Backend returned invalid {context} format: expected list, got {type(data).__name__}"
        )
        logger.error(f"{error_msg}. Value: {data!r}")
        return [], error_msg

    # Validate each item is a dict
    validated = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                f"Invalid {context} item at index {i}: expected dict, got {type(item).__name__}. Skipping."
            )
            continue
        validated.append(item)

    return validated, None


def validate_dict_response(
    response: ApiResponse, context: str
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate that an API response contains a dictionary.

    Args:
        response: The API response to validate
        context: Description of what we're fetching (e.g., "task", "project")

    Returns:
        Tuple of (validated dict or None, error message or None)
    """
    if not response.success:
        return None, response.error or f"Failed to fetch {context}"

    data = response.data
    if data is None:
        return None, f"No {context} data returned from backend"

    if not isinstance(data, dict):
        error_msg = (
            f"Backend returned invalid {context} format: expected dict, got {type(data).__name__}"
        )
        logger.error(f"{error_msg}. Value: {data!r}")
        return None, error_msg

    return data, None


class NormalizePathMiddleware:
    """ASGI middleware to normalize paths so /mcp and /mcp/ work identically.

    Strips trailing slashes from all paths (except root) before routing.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        if scope["type"] == "http":
            path = scope.get("path", "/")
            # Normalize: strip trailing slash if path is not just "/"
            if path != "/" and path.endswith("/"):
                scope = dict(scope)
                scope["path"] = path.rstrip("/")
        await self.app(scope, receive, send)


def create_logging_middleware(app: Any) -> Callable[[dict[str, Any], Any, Any], Any]:
    """Create ASGI middleware to log detailed request information for debugging.

    Uses raw ASGI interface to avoid interfering with request body or streaming.
    """

    async def middleware(scope: dict[str, Any], receive: Any, send: Any) -> Any:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        # Extract request info from scope
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}

        # Log request details
        logger.info("=" * 60)
        logger.info(f"=== Incoming Request: {method} {path} ===")
        if query_string:
            logger.info(f"Query string: {query_string}")
        logger.info(f"Client: {scope.get('client')}")

        # Log all headers
        logger.info("Headers:")
        for name, value in headers.items():
            # Mask authorization header value for security
            if name.lower() == "authorization":
                logger.info(f"  {name}: Bearer ***")
            else:
                logger.info(f"  {name}: {value}")

        # Log specific headers that MCP cares about
        content_type = headers.get("content-type", "NOT SET")
        origin = headers.get("origin", "NOT SET")
        host = headers.get("host", "NOT SET")
        mcp_session = headers.get("mcp-session-id", "NOT SET")
        mcp_protocol = headers.get("mcp-protocol-version", "NOT SET")

        logger.info("Key MCP headers:")
        logger.info(f"  Content-Type: {content_type}")
        logger.info(f"  Origin: {origin}")
        logger.info(f"  Host: {host}")
        logger.info(f"  Mcp-Session-Id: {mcp_session}")
        logger.info(f"  Mcp-Protocol-Version: {mcp_protocol}")

        # Track response status
        response_status = [None]
        response_headers: list[dict[str, str]] = [{}]

        async def send_wrapper(message: dict[str, Any]) -> Any:
            if message["type"] == "http.response.start":
                response_status[0] = message.get("status")
                response_headers[0] = {
                    k.decode(): v.decode() for k, v in message.get("headers", [])
                }

                # Log response status
                logger.info(f"=== Response: {response_status[0]} for {method} {path} ===")

                # If it's a 400 error, log more details
                if response_status[0] == 400:
                    logger.error("!!! 400 Bad Request returned !!!")
                    logger.error(f"Response headers: {response_headers[0]}")

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and response_status[0] == 400:
                    # Log the response body for 400 errors
                    body_text = body.decode("utf-8", errors="replace")
                    logger.error(f"400 Response body: {body_text}")

            await send(message)

        # Log body for POST requests by wrapping receive
        body_logged = [False]

        async def receive_with_logging() -> Any:
            message = await receive()
            if message["type"] == "http.request" and not body_logged[0]:
                body_logged[0] = True
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if body:
                    body_preview = body[:1000].decode("utf-8", errors="replace")
                    if len(body) > 1000 or more_body:
                        body_preview += "... (truncated/more coming)"
                    logger.info(f"Request body preview ({len(body)} bytes): {body_preview}")
            return message

        logger.info("=" * 60)

        if method == "POST":
            await app(scope, receive_with_logging, send_wrapper)
        else:
            await app(scope, receive, send_wrapper)

    return middleware


DEFAULT_SCOPE = ["read"]

load_dotenv()
# OAuth client credentials (for MCP OAuth flow)
CLIENT_ID = os.environ["TASKMANAGER_CLIENT_ID"]
CLIENT_SECRET = os.environ["TASKMANAGER_CLIENT_SECRET"]
MCP_AUTH_SERVER = os.environ["MCP_AUTH_SERVER"]

# TaskManager API URL
TASKMANAGER_URL = os.environ.get("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")

# User credentials for API access
USERNAME = os.environ.get("TASKMANAGER_USERNAME", CLIENT_ID)
PASSWORD = os.environ.get("TASKMANAGER_PASSWORD", CLIENT_SECRET)


def get_api_client() -> TaskManagerClient:
    """Get API client for authenticated user.

    Currently uses server credentials for all requests.
    In a production system, this should be modified to use
    user-specific authentication tokens.

    Returns:
        TaskManagerClient: Authenticated API client

    Raises:
        AuthenticationError: If authentication fails
        NetworkError: If unable to connect to backend
    """
    # Use the public TaskManager URL for API calls
    task_manager = TaskManagerClient(base_url=f"{TASKMANAGER_URL}/api")

    # Use username/password for API authentication
    # SDK raises AuthenticationError on failure
    task_manager.login(USERNAME, PASSWORD)
    logger.debug("Successfully authenticated with TaskManager API")
    return task_manager


def create_resource_server(
    port: int,
    server_url: str,
    auth_server_url: str,
    auth_server_public_url: str,
    oauth_strict: bool,
) -> FastMCP:
    """
    Create MCP Resource Server with token introspection.

    This server:
    1. Provides public MCP transport endpoint (/mcp) for discovery
    2. Validates tokens via Authorization Server introspection for tools
    3. Serves protected MCP tools and resources

    Args:
        port: Port to listen on
        server_url: Public URL of this server
        auth_server_url: Internal auth server URL (for introspection)
        auth_server_public_url: Public auth server URL (for OAuth metadata)
        oauth_strict: Enable RFC 8707 resource validation
    """
    # Create token verifier for introspection with RFC 8707 resource validation
    # Use internal URL for introspection (server-to-server communication)
    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=f"{auth_server_url}/introspect",
        server_url=str(server_url),
        validate_resource=oauth_strict,  # Enable RFC 8707 resource validation when --oauth-strict is set
    )

    # Extract hostname from server_url for transport security
    parsed_url = urlparse(server_url)
    allowed_host = parsed_url.netloc  # e.g., "mcp.brooksmcmillin.com"

    # Create FastMCP server with OAuth-protected endpoints
    # Use public auth server URL for OAuth flows
    # Configure transport_security to allow requests from the public hostname
    app = FastMCP(
        name="TaskManager MCP Server",
        instructions="TaskManager MCP Server with OAuth-protected tools and resources",
        port=port,
        debug=True,
        token_verifier=token_verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(auth_server_public_url),
            required_scopes=DEFAULT_SCOPE,
            resource_server_url=AnyHttpUrl(server_url),
        ),
        transport_security=TransportSecuritySettings(
            allowed_hosts=[allowed_host],
        ),
    )

    # CORS middleware will be added when we run the server with uvicorn

    # Add OAuth 2.0 discovery endpoints for client auto-configuration
    # These endpoints allow MCP clients to discover OAuth configuration automatically

    @app.custom_route("/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource_main(request: Request) -> JSONResponse:
        """OAuth 2.0 Protected Resource Metadata (RFC 9908) - Main endpoint"""
        logger.info("=== OAuth Protected Resource Metadata Request (Main) ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Host header: {request.headers.get('host')}")

        # Remove trailing slashes for OAuth spec compliance
        resource_url = str(server_url).rstrip("/")
        auth_server_url_no_slash = str(auth_server_public_url).rstrip("/")

        logger.info(f"Returning resource: {resource_url}")
        logger.info(f"Returning auth_servers: {auth_server_url_no_slash}")

        return JSONResponse(
            {
                "resource": resource_url,
                "authorization_servers": [auth_server_url_no_slash],
                "scopes_supported": DEFAULT_SCOPE,
                "bearer_methods_supported": ["header"],
            }
        )

    @app.custom_route("/.well-known/openid-configuration", methods=["GET", "OPTIONS"])
    async def openid_configuration(request: Request) -> JSONResponse:
        """OpenID Connect Discovery (aliases to OAuth Authorization Server Metadata)"""
        # Handle CORS preflight
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        # OpenID Connect discovery - return same metadata as OAuth
        auth_base = str(auth_server_public_url).rstrip("/")

        logger.info("=== OpenID Configuration Request ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Host header: {request.headers.get('host')}")
        logger.info(f"Returning issuer: {auth_base}")

        return JSONResponse(
            {
                "issuer": auth_base,
                "authorization_endpoint": f"{auth_base}/authorize",
                "token_endpoint": f"{auth_base}/token",
                "introspection_endpoint": f"{auth_base}/introspect",
                "registration_endpoint": f"{auth_base}/register",
                "scopes_supported": DEFAULT_SCOPE,
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "code_challenge_methods_supported": ["S256"],
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    @app.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def oauth_authorization_server_metadata(request: Request) -> JSONResponse:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
        # Handle CORS preflight
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        # Use public auth server URL for client-facing OAuth metadata
        # Remove trailing slash for OAuth spec compliance
        auth_base = str(auth_server_public_url).rstrip("/")

        logger.info("=== OAuth Authorization Server Metadata Request ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Host header: {request.headers.get('host')}")
        logger.info(f"X-Forwarded-Proto: {request.headers.get('x-forwarded-proto')}")
        logger.info(f"X-Forwarded-For: {request.headers.get('x-forwarded-for')}")
        logger.info(f"Returning auth_base: {auth_base}")

        return JSONResponse(
            {
                "issuer": auth_base,
                "authorization_endpoint": f"{auth_base}/authorize",
                "token_endpoint": f"{auth_base}/token",
                "introspection_endpoint": f"{auth_base}/introspect",
                "registration_endpoint": f"{auth_base}/register",
                "scopes_supported": DEFAULT_SCOPE,
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "code_challenge_methods_supported": ["S256"],
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    @app.custom_route("/mcp/.well-known/oauth-protected-resource", methods=["GET"])
    async def oauth_protected_resource_metadata(request: Request) -> JSONResponse:
        """OAuth 2.0 Protected Resource Metadata (RFC 9908)"""
        logger.info("=== OAuth Protected Resource Metadata Request (MCP-specific) ===")
        logger.info(f"Request URL: {request.url}")
        logger.info(f"Host header: {request.headers.get('host')}")
        logger.info(f"Returning resource: {server_url}")
        logger.info(f"Returning auth_servers: {auth_server_public_url}")

        # Remove trailing slashes for OAuth spec compliance
        resource_url = str(server_url).rstrip("/")
        auth_server_url_no_slash = str(auth_server_public_url).rstrip("/")

        return JSONResponse(
            {
                "resource": resource_url,
                "authorization_servers": [auth_server_url_no_slash],
                "scopes_supported": DEFAULT_SCOPE,
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{resource_url}/docs",
            }
        )

    @app.custom_route("/.well-known/oauth-authorization-server/mcp", methods=["GET"])
    async def oauth_authorization_server_metadata_for_mcp(
        request: Request,
    ) -> JSONResponse:
        """Resource-specific OAuth 2.0 Authorization Server Metadata for /mcp resource"""
        # Use public auth server URL for client-facing OAuth metadata
        # Remove trailing slash for OAuth spec compliance
        auth_base = str(auth_server_public_url).rstrip("/")
        resource_url = str(server_url).rstrip("/")

        return JSONResponse(
            {
                "issuer": auth_base,
                "authorization_endpoint": f"{auth_base}/authorize",
                "token_endpoint": f"{auth_base}/token",
                "introspection_endpoint": f"{auth_base}/introspect",
                "registration_endpoint": f"{auth_base}/register",
                "scopes_supported": DEFAULT_SCOPE,
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "token_endpoint_auth_methods_supported": ["client_secret_post"],
                "code_challenge_methods_supported": ["S256"],
                "resource": resource_url,  # Resource-specific binding
            }
        )

    @app.tool()
    async def get_time() -> dict[str, Any]:
        """
        Get the current server time.

        This tool demonstrates that system information can be protected
        by OAuth authentication. User must be authenticated to access it.
        """
        # This tool is protected by OAuth authentication at the transport level
        # All requests to /mcp require a valid Bearer token

        now = datetime.datetime.now()

        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",  # Simplified for demo
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @app.tool()
    async def check_task_system_status() -> dict[str, Any]:
        """
        Check the health and operational status of the task management backend.

        Verifies connectivity to the backend API and returns status information
        about each major subsystem. Use this tool before performing operations
        to diagnose system availability issues.

        Returns:
            JSON object with overall status and individual component checks:
            - overall_status: "healthy", "degraded", or "unhealthy"
            - backend_api: Backend API connectivity status
            - projects_service: Projects/categories service status
            - tasks_service: Tasks service status
            - timestamp: When the check was performed
            - message: Human-readable status summary
        """
        logger.info("=== check_task_system_status called ===")
        now = datetime.datetime.now()
        checks: dict[str, dict[str, Any]] = {}
        errors: list[str] = []

        try:
            api_client = get_api_client()

            # Check projects service
            try:
                projects_response = api_client.get_projects()
                if projects_response.success:
                    projects, proj_error = validate_list_response(projects_response, "projects")
                    if proj_error:
                        checks["projects_service"] = {
                            "status": "degraded",
                            "error": proj_error,
                        }
                        errors.append(f"Projects service: {proj_error}")
                    else:
                        checks["projects_service"] = {
                            "status": "healthy",
                            "project_count": len(projects),
                        }
                else:
                    checks["projects_service"] = {
                        "status": "unhealthy",
                        "error": projects_response.error or "Request failed",
                        "status_code": projects_response.status_code,
                    }
                    errors.append(f"Projects service: {projects_response.error}")
            except Exception as e:
                checks["projects_service"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                errors.append(f"Projects service: {e}")

            # Check tasks service
            try:
                tasks_response = api_client.get_todos()
                if tasks_response.success:
                    tasks, task_error = validate_list_response(tasks_response, "tasks")
                    if task_error:
                        checks["tasks_service"] = {
                            "status": "degraded",
                            "error": task_error,
                        }
                        errors.append(f"Tasks service: {task_error}")
                    else:
                        checks["tasks_service"] = {
                            "status": "healthy",
                            "task_count": len(tasks),
                        }
                else:
                    checks["tasks_service"] = {
                        "status": "unhealthy",
                        "error": tasks_response.error or "Request failed",
                        "status_code": tasks_response.status_code,
                    }
                    errors.append(f"Tasks service: {tasks_response.error}")
            except Exception as e:
                checks["tasks_service"] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                errors.append(f"Tasks service: {e}")

            # Backend API is reachable if we got here
            checks["backend_api"] = {"status": "healthy"}

        except Exception as e:
            # Complete backend failure
            logger.error(f"Backend connectivity check failed: {e}", exc_info=True)
            checks["backend_api"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            checks["projects_service"] = {"status": "unknown"}
            checks["tasks_service"] = {"status": "unknown"}
            errors.append(f"Backend API: {e}")

        # Determine overall status
        statuses = [c.get("status") for c in checks.values()]
        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
            message = "All systems operational"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
            message = f"System errors detected: {'; '.join(errors)}"
        else:
            overall_status = "degraded"
            message = f"Some issues detected: {'; '.join(errors)}"

        logger.info(f"Health check result: {overall_status}")
        return {
            "overall_status": overall_status,
            "backend_api": checks.get("backend_api", {}),
            "projects_service": checks.get("projects_service", {}),
            "tasks_service": checks.get("tasks_service", {}),
            "timestamp": now.isoformat(),
            "message": message,
        }

    @app.tool()
    async def get_tasks(
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        category: str | None = None,
        limit: int | None = None,
    ) -> str:
        """
        Retrieve tasks with filtering options.

        Args:
            status: Filter by status - one of "pending", "in_progress", "completed", "cancelled", "overdue", or "all"
            start_date: Filter tasks with due date on or after this date (ISO format, e.g., "2025-12-14")
            end_date: Filter tasks with due date on or before this date (ISO format, e.g., "2025-12-20")
            category: Filter by category/project name
            limit: Maximum number of tasks to return

        Returns:
            JSON object with "tasks" array containing task objects with fields:
            id, title, description, due_date, status, category, priority, tags, created_at, updated_at
        """
        logger.info(
            f"=== get_tasks called: status={status}, start_date={start_date}, "
            f"end_date={end_date}, category={category}, limit={limit} ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # SDK handles all filtering server-side
            response = api_client.get_todos(
                status=status if status and status.lower() != "all" else None,
                start_date=start_date,
                end_date=end_date,
                category=category,
                limit=limit,
            )
            logger.info(
                f"get_todos response: success={response.success}, status={response.status_code}"
            )

            tasks, tasks_error = validate_list_response(response, "tasks")
            if tasks_error:
                logger.error(f"Failed to get tasks: {tasks_error}")
                return json.dumps({"error": tasks_error})

            logger.info(f"Retrieved {len(tasks)} tasks")

            # Transform tasks to match expected output format
            result_tasks = []
            for task in tasks:
                task_id = task.get("id")
                if task_id is None:
                    continue  # Skip tasks without valid ID
                result_tasks.append(
                    {
                        "id": f"task_{task_id}",
                        "title": task.get("title", ""),
                        "description": task.get("description"),
                        "due_date": task.get("due_date"),
                        "status": task.get("status", "pending"),
                        "category": task.get("project_name") or task.get("category"),
                        "priority": task.get("priority", "medium"),
                        "tags": task.get("tags") or [],
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                    }
                )

            logger.info(f"Returning {len(result_tasks)} tasks")
            return json.dumps({"tasks": result_tasks})
        except Exception as e:
            logger.error(f"Exception in get_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    async def create_task(
        title: str,
        description: str | None = None,
        due_date: str | None = None,
        category: str | None = None,
        priority: str = "medium",
        tags: list[str] | None = None,
    ) -> str:
        """
        Create a new task.

        Args:
            title: Task title (required)
            description: Task details (optional)
            due_date: Due date in ISO format, e.g., "2025-12-20" (optional)
            category: Task category/project name (optional)
            priority: Priority level - one of "low", "medium", "high", "urgent" (default: "medium")
            tags: List of task tags (optional)

        Returns:
            JSON object with id, title, and status fields confirming task creation
        """
        logger.info(
            f"=== create_task called: title='{title}', category={category}, priority={priority} ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # SDK handles category-to-project mapping
            response = api_client.create_todo(
                title=title,
                category=category,
                description=description,
                priority=priority,
                due_date=due_date,
                tags=tags,
            )
            logger.info(
                f"create_todo response: success={response.success}, status={response.status_code}"
            )

            task, task_error = validate_dict_response(response, "created task")
            if task_error:
                logger.error(f"Failed to create task: {task_error}")
                return json.dumps({"error": task_error})

            logger.info(f"Created task: {task}")

            # Return response in expected format
            task_id = task.get("id") if task is not None else None
            if task_id is None:
                logger.warning("Task data missing 'id' field")
                return json.dumps({"error": "Created task has no ID"})

            result = {
                "id": f"task_{task_id}",
                "title": task.get("title", title) if task is not None else title,
                "status": "created",
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in create_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    async def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Update an existing task.

        Args:
            task_id: Task ID (required) - format "task_123" or just "123"
            title: New title (optional)
            description: New description (optional)
            due_date: New due date in ISO format for rescheduling (optional)
            status: New status - one of "pending", "in_progress", "completed", "cancelled" (optional)
            category: New category/project name (optional)
            priority: New priority - one of "low", "medium", "high", "urgent" (optional)
            tags: New list of tags (optional)

        Returns:
            JSON object with id, updated_fields list, and status confirming update
        """
        logger.info(f"=== update_task called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id (handle both "task_123" and "123" formats)
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Track which fields are being updated
            updated_fields = []
            if title is not None:
                updated_fields.append("title")
            if description is not None:
                updated_fields.append("description")
            if due_date is not None:
                updated_fields.append("due_date")
            if status is not None:
                updated_fields.append("status")
            if category is not None:
                updated_fields.append("category")
            if priority is not None:
                updated_fields.append("priority")
            if tags is not None:
                updated_fields.append("tags")

            # SDK handles category-to-project mapping
            response = api_client.update_todo(
                todo_id=todo_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                status=status,
                due_date=due_date,
                tags=tags,
            )
            logger.info(
                f"update_todo response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to update task: {response.error}")
                return json.dumps({"error": response.error})

            # Return response in expected format
            result = {
                "id": f"task_{todo_id}",
                "updated_fields": updated_fields,
                "status": "updated",
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in update_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    async def get_categories() -> str:
        """
        List all available task categories.

        Returns a list of all categories (projects) with the count of tasks in each.

        Returns:
            JSON object with "categories" array containing objects with name and task_count fields
        """
        logger.info("=== get_categories called ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # SDK provides dedicated endpoint with task counts
            response = api_client.get_categories()
            logger.info(
                f"get_categories response: success={response.success}, status={response.status_code}"
            )

            categories, categories_error = validate_list_response(response, "categories")
            if categories_error:
                logger.error(f"Failed to get categories: {categories_error}")
                return json.dumps({"error": categories_error})

            logger.info(f"Returning {len(categories)} categories")
            return json.dumps({"categories": categories})
        except Exception as e:
            logger.error(f"Exception in get_categories: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    async def search_tasks(
        query: str,
        category: str | None = None,
    ) -> str:
        """
        Search tasks by keyword using full-text search.

        Searches task titles, descriptions, and tags for the given query string.

        Args:
            query: Search query string (required)
            category: Filter by category/project name (optional)

        Returns:
            JSON object with "tasks" array (same format as get_tasks) and "count" field
        """
        logger.info(f"=== search_tasks called: query='{query}', category={category} ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # SDK provides dedicated full-text search endpoint
            response = api_client.search_tasks(query=query, category=category)
            logger.info(
                f"search_tasks response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to search tasks: {response.error}")
                return json.dumps({"error": response.error})

            data = response.data
            if data is None:
                return json.dumps({"tasks": [], "count": 0})

            # Handle response format (could be list or dict with 'tasks' key)
            if isinstance(data, list):
                tasks = data
            elif isinstance(data, dict):
                tasks = data.get("tasks", [])
            else:
                logger.warning(f"Unexpected search response format: {type(data)}")
                tasks = []

            # Transform tasks to match expected output format
            result_tasks = []
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                task_id = task.get("id")
                if task_id is None:
                    continue
                result_tasks.append(
                    {
                        "id": f"task_{task_id}",
                        "title": task.get("title", ""),
                        "description": task.get("description"),
                        "due_date": task.get("due_date"),
                        "status": task.get("status", "pending"),
                        "category": task.get("project_name") or task.get("category"),
                        "priority": task.get("priority", "medium"),
                        "tags": task.get("tags") or [],
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                    }
                )

            logger.info(f"Found {len(result_tasks)} tasks matching query '{query}'")
            return json.dumps({"tasks": result_tasks, "count": len(result_tasks)})
        except Exception as e:
            logger.error(f"Exception in search_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    return app


@click.command()
@click.option("--port", default=8001, help="Port to listen on")
@click.option(
    "--auth-server",
    default=MCP_AUTH_SERVER,
    help="Authorization Server URL (internal, for introspection)",
)
@click.option(
    "--auth-server-public-url",
    help="Public Authorization Server URL (for OAuth metadata). Defaults to --auth-server value",
)
@click.option(
    "--server-url",
    help="External server URL (for OAuth). Defaults to https://localhost:PORT",
)
@click.option(
    "--oauth-strict",
    is_flag=True,
    help="Enable RFC 8707 resource validation",
)
def main(
    port: int,
    auth_server: str,
    auth_server_public_url: str | None = None,
    server_url: str | None = None,
    oauth_strict: bool = False,
) -> int:
    """
    Run the TaskManager MCP server.

    Args:
        port: Port to bind the server to
        auth_server: URL of the OAuth authorization server
        server_url: Public URL of this server (for OAuth callbacks)
        oauth_strict: Enable RFC 8707 resource validation

    Returns:
        Exit code (0 for success, 1 for error)
    """

    # Configure logging with timestamps for all loggers including uvicorn
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    # Also configure uvicorn loggers to use the same format
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        uv_logger.addHandler(handler)

    try:
        # If no server specified, use environment variable or default
        if server_url is None:
            server_url = os.getenv("MCP_SERVER_URL", f"https://localhost:{port}")

        # If no public auth server URL specified, use environment variable or default to internal URL
        if auth_server_public_url is None:
            auth_server_public_url = os.getenv("MCP_AUTH_SERVER_PUBLIC_URL", auth_server)

        # Remove trailing slashes from URLs (OAuth spec compliance)
        server_url = server_url.rstrip("/")
        auth_server_public_url = auth_server_public_url.rstrip("/")

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Make sure to provide a valid Authorization Server URL")
        return 1

    try:
        mcp_server = create_resource_server(
            port, server_url, auth_server, auth_server_public_url, oauth_strict
        )

        logger.info("=" * 60)
        logger.info(f"🚀 MCP Resource Server running on {server_url}")
        logger.info(f"🔑 Using Authorization Server (internal): {auth_server}")
        logger.info(f"🌐 Using Authorization Server (public): {auth_server_public_url}")
        logger.info(f"📍 Resource Server URL (for OAuth): {server_url}")
        logger.info("=" * 60)

        # Run the server - bind to 0.0.0.0 for Docker networking
        # FastMCP handles CORS internally for discovery endpoints
        import uvicorn

        # Get the Starlette app (streamable_http_app is a method, not a property)
        starlette_app = mcp_server.streamable_http_app()

        # Wrap app with middleware so /mcp and /mcp/ work identically
        app = NormalizePathMiddleware(starlette_app)

        # Configure uvicorn to handle proxy headers properly
        uvicorn.run(
            app,
            host="0.0.0.0",  # noqa: S104
            port=port,
            log_level="debug",
            proxy_headers=False,
            # forwarded_allow_ips="127.0.0.1",
            access_log=True,
        )
        logger.info("Server stopped")
        return 0
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Exception details:")
        return 1


if __name__ == "__main__":
    main()
