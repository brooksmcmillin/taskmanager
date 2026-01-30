import datetime
import json
import logging
import os
from typing import Any
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.middleware import NormalizePathMiddleware
from mcp_resource_framework.security import guard_tool
from mcp_resource_framework.validation import validate_dict_response, validate_list_response
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse
from taskmanager_sdk import TaskManagerClient

logger = logging.getLogger(__name__)

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

# CORS allowed origins for OAuth discovery endpoints
# Parse from comma-separated environment variable, or use empty list to block all origins
ALLOWED_MCP_ORIGINS = (
    os.getenv("ALLOWED_MCP_ORIGINS", "").split(",") if os.getenv("ALLOWED_MCP_ORIGINS") else []
)
# Remove empty strings and strip whitespace
ALLOWED_MCP_ORIGINS = [origin.strip() for origin in ALLOWED_MCP_ORIGINS if origin.strip()]


def get_cors_origin(request: Request) -> str:
    """
    Get CORS origin header value based on request origin.

    Only returns the origin if it's in the allowed list, otherwise returns empty string
    to deny CORS access.

    Args:
        request: The incoming request

    Returns:
        Origin value for Access-Control-Allow-Origin header
    """
    request_origin = request.headers.get("origin", "")
    if request_origin in ALLOWED_MCP_ORIGINS:
        return request_origin
    # If no allowed origins configured, deny all CORS (return empty string)
    # If origin not in allowed list, deny (return empty string)
    return ""


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
    # Debug mode controlled by DEBUG environment variable
    debug_mode = os.getenv("DEBUG", "false").lower() == "true"

    app = FastMCP(
        name="TaskManager MCP Server",
        instructions="TaskManager MCP Server with OAuth-protected tools and resources",
        port=port,
        debug=debug_mode,
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
        # Handle CORS preflight with origin validation
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": get_cors_origin(request),
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
                "Access-Control-Allow-Origin": get_cors_origin(request),
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    @app.custom_route("/.well-known/oauth-authorization-server", methods=["GET", "OPTIONS"])
    async def oauth_authorization_server_metadata(request: Request) -> JSONResponse:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414)"""
        # Handle CORS preflight with origin validation
        if request.method == "OPTIONS":
            return JSONResponse(
                {},
                headers={
                    "Access-Control-Allow-Origin": get_cors_origin(request),
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
                "Access-Control-Allow-Origin": get_cors_origin(request),
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
    @guard_tool(input_params=[], screen_output=True)
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
            "current_time": now.isoformat(),
            "message": message,
        }

    @app.tool()
    @guard_tool(input_params=["status", "category"], screen_output=True)
    async def get_tasks(
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        category: str | None = None,
        limit: int | None = None,
        include_subtasks: bool = True,
    ) -> str:
        """
        Retrieve tasks with filtering options.

        Args:
            status: Filter by status - one of "pending", "in_progress", "completed", "cancelled", "overdue", or "all"
            start_date: Filter tasks with due date on or after this date (ISO format, e.g., "2025-12-14")
            end_date: Filter tasks with due date on or before this date (ISO format, e.g., "2025-12-20")
            category: Filter by category/project name
            limit: Maximum number of tasks to return
            include_subtasks: Whether to include subtasks in the response (default: True)

        Returns:
            JSON object with "tasks" array containing task objects with fields:
            id, title, description, due_date, status, category, priority, tags, parent_id, subtasks, created_at, updated_at
        """
        logger.info(
            f"=== get_tasks called: status={status}, start_date={start_date}, "
            f"end_date={end_date}, category={category}, limit={limit}, include_subtasks={include_subtasks} ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # SDK handles all filtering server-side
            # Add include_subtasks parameter
            params: dict[str, str | int | bool] = {}
            if status and status.lower() != "all":
                params["status"] = status
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            if category:
                params["category"] = category
            if limit:
                params["limit"] = limit
            if include_subtasks:
                params["include_subtasks"] = True

            response = api_client._make_request("GET", "/todos", params=params)
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

                # Transform subtasks if present
                subtasks_list = []
                if task.get("subtasks"):
                    for subtask in task["subtasks"]:
                        subtasks_list.append(
                            {
                                "id": f"task_{subtask.get('id')}",
                                "title": subtask.get("title", ""),
                                "description": subtask.get("description"),
                                "status": subtask.get("status", "pending"),
                                "priority": subtask.get("priority", "medium"),
                                "due_date": subtask.get("due_date"),
                                "estimated_hours": subtask.get("estimated_hours"),
                                "actual_hours": subtask.get("actual_hours"),
                                "created_at": subtask.get("created_at"),
                                "updated_at": subtask.get("updated_at"),
                            }
                        )

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
                        "parent_id": f"task_{task.get('parent_id')}"
                        if task.get("parent_id")
                        else None,
                        "subtasks": subtasks_list,
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                    }
                )

            logger.info(f"Returning {len(result_tasks)} tasks")
            return json.dumps(
                {
                    "tasks": result_tasks,
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["title", "description", "category", "tags"], screen_output=True)
    async def create_task(
        title: str,
        description: str | None = None,
        due_date: str | None = None,
        category: str | None = None,
        priority: str = "medium",
        tags: list[str] | None = None,
        parent_id: str | None = None,
    ) -> str:
        """
        Create a new task or subtask.

        Args:
            title: Task title (required)
            description: Task details (optional)
            due_date: Due date in ISO format, e.g., "2025-12-20" (optional)
            category: Task category/project name (optional)
            priority: Priority level - one of "low", "medium", "high", "urgent" (default: "medium")
            tags: List of task tags (optional)
            parent_id: Parent task ID to create a subtask - format "task_123" or just "123" (optional)

        Returns:
            JSON object with id, title, and status fields confirming task creation
        """
        logger.info(
            f"=== create_task called: title='{title}', category={category}, priority={priority}, parent_id={parent_id} ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Convert parent_id if provided
            parent_id_int: int | None = None
            if parent_id:
                numeric_id = (
                    parent_id.replace("task_", "") if parent_id.startswith("task_") else parent_id
                )
                try:
                    parent_id_int = int(numeric_id)
                except ValueError:
                    return json.dumps({"error": f"Invalid parent_id format: {parent_id}"})

            # Build request data
            data: dict[str, str | int | list[str]] = {"title": title}
            if description:
                data["description"] = description
            if category:
                data["category"] = category
            if priority:
                data["priority"] = priority
            if due_date:
                data["due_date"] = due_date
            if tags:
                data["tags"] = tags
            if parent_id_int:
                data["parent_id"] = parent_id_int

            response = api_client._make_request("POST", "/todos", data)
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
                "parent_id": f"task_{parent_id_int}" if parent_id_int else None,
                "current_time": datetime.datetime.now().isoformat(),
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in create_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(
        input_params=["title", "description", "status", "category", "tags"],
        screen_output=True,
    )
    async def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        parent_id: str | None = None,
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
            parent_id: New parent task ID to move task - format "task_123" or just "123" (optional)

        Returns:
            JSON object with id, updated_fields list, and status confirming update
        """
        logger.info(f"=== update_task called: task_id='{task_id}', parent_id={parent_id} ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id (handle both "task_123" and "123" formats)
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Convert parent_id if provided
            parent_id_int: int | None = None
            if parent_id:
                parent_numeric_id = (
                    parent_id.replace("task_", "") if parent_id.startswith("task_") else parent_id
                )
                try:
                    parent_id_int = int(parent_numeric_id)
                except ValueError:
                    return json.dumps({"error": f"Invalid parent_id format: {parent_id}"})

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
            if parent_id is not None:
                updated_fields.append("parent_id")

            # Build request data
            data: dict[str, str | int | list[str]] = {}
            if title is not None:
                data["title"] = title
            if description is not None:
                data["description"] = description
            if category is not None:
                data["category"] = category
            if priority is not None:
                data["priority"] = priority
            if status is not None:
                data["status"] = status
            if due_date is not None:
                data["due_date"] = due_date
            if tags is not None:
                data["tags"] = tags
            if parent_id_int is not None:
                data["parent_id"] = parent_id_int

            response = api_client._make_request("PUT", f"/todos/{todo_id}", data)
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
                "current_time": datetime.datetime.now().isoformat(),
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in update_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
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
            return json.dumps(
                {
                    "categories": categories,
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_categories: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["query", "category"], screen_output=True)
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

                # Transform subtasks if present
                subtasks_list = []
                if task.get("subtasks"):
                    for subtask in task["subtasks"]:
                        subtasks_list.append(
                            {
                                "id": f"task_{subtask.get('id')}",
                                "title": subtask.get("title", ""),
                                "description": subtask.get("description"),
                                "status": subtask.get("status", "pending"),
                                "priority": subtask.get("priority", "medium"),
                                "due_date": subtask.get("due_date"),
                                "estimated_hours": subtask.get("estimated_hours"),
                                "actual_hours": subtask.get("actual_hours"),
                                "created_at": subtask.get("created_at"),
                                "updated_at": subtask.get("updated_at"),
                            }
                        )

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
                        "parent_id": f"task_{task.get('parent_id')}"
                        if task.get("parent_id")
                        else None,
                        "subtasks": subtasks_list,
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                    }
                )

            logger.info(f"Found {len(result_tasks)} tasks matching query '{query}'")
            return json.dumps(
                {
                    "tasks": result_tasks,
                    "count": len(result_tasks),
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in search_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def list_task_attachments(task_id: str) -> str:
        """
        List all attachments for a specific task.

        Args:
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object with "attachments" array containing attachment objects with fields:
            id, filename, content_type, file_size, created_at
        """
        logger.info(f"=== list_task_attachments called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Get attachments
            response = api_client._make_request("GET", f"/todos/{todo_id}/attachments")
            logger.info(
                f"list_attachments response: success={response.success}, status={response.status_code}"
            )

            attachments, attachments_error = validate_list_response(response, "attachments")
            if attachments_error:
                logger.error(f"Failed to get attachments: {attachments_error}")
                return json.dumps({"error": attachments_error})

            logger.info(f"Returning {len(attachments)} attachments")
            return json.dumps(
                {
                    "task_id": task_id,
                    "attachments": attachments,
                    "count": len(attachments),
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_task_attachments: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def delete_task_attachment(task_id: str, attachment_id: int) -> str:
        """
        Delete an attachment from a task.

        Args:
            task_id: Task ID - format "task_123" or just "123"
            attachment_id: Attachment ID to delete

        Returns:
            JSON object confirming deletion with deleted status and id
        """
        logger.info(
            f"=== delete_task_attachment called: task_id='{task_id}', attachment_id={attachment_id} ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Delete attachment
            response = api_client._make_request(
                "DELETE", f"/todos/{todo_id}/attachments/{attachment_id}"
            )
            logger.info(
                f"delete_attachment response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to delete attachment: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Deleted attachment {attachment_id} from task {task_id}")
            return json.dumps(
                {
                    "task_id": task_id,
                    "attachment_id": attachment_id,
                    "status": "deleted",
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in delete_task_attachment: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_task(task_id: str) -> str:
        """
        Get a single task by ID with full details.

        Retrieves complete task information including subtasks, attachments count,
        and all metadata. More efficient than filtering get_tasks for a specific task.

        Args:
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object with task data including:
            id, title, description, status, priority, due_date, category,
            tags, parent_id, subtasks, estimated_hours, actual_hours,
            created_at, updated_at, current_time
        """
        logger.info(f"=== get_task called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Get task details
            response = api_client._make_request("GET", f"/todos/{todo_id}")
            logger.info(
                f"get_todo response: success={response.success}, status={response.status_code}"
            )

            task, task_error = validate_dict_response(response, "task")
            if task_error or task is None:
                logger.error(f"Failed to get task: {task_error}")
                return json.dumps({"error": task_error or "Task not found"})

            logger.info(f"Retrieved task: {task.get('id')}")

            # Transform subtasks if present
            subtasks_list = []
            if task.get("subtasks"):
                for subtask in task["subtasks"]:
                    subtasks_list.append(
                        {
                            "id": f"task_{subtask.get('id')}",
                            "title": subtask.get("title", ""),
                            "description": subtask.get("description"),
                            "status": subtask.get("status", "pending"),
                            "priority": subtask.get("priority", "medium"),
                            "due_date": subtask.get("due_date"),
                            "estimated_hours": subtask.get("estimated_hours"),
                            "actual_hours": subtask.get("actual_hours"),
                            "created_at": subtask.get("created_at"),
                            "updated_at": subtask.get("updated_at"),
                        }
                    )

            # Build response
            result = {
                "task": {
                    "id": f"task_{task.get('id')}",
                    "title": task.get("title", ""),
                    "description": task.get("description"),
                    "due_date": task.get("due_date"),
                    "status": task.get("status", "pending"),
                    "category": task.get("project_name") or task.get("category"),
                    "priority": task.get("priority", "medium"),
                    "tags": task.get("tags") or [],
                    "parent_id": (
                        f"task_{task.get('parent_id')}" if task.get("parent_id") else None
                    ),
                    "subtasks": subtasks_list,
                    "estimated_hours": task.get("estimated_hours"),
                    "actual_hours": task.get("actual_hours"),
                    "created_at": task.get("created_at"),
                    "updated_at": task.get("updated_at"),
                },
                "current_time": datetime.datetime.now().isoformat(),
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in get_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def delete_task(task_id: str) -> str:
        """
        Delete a task (soft delete).

        Moves the task to trash by setting a deletion timestamp. The task can
        potentially be restored later. All subtasks are also deleted.

        Args:
            task_id: Task ID to delete - format "task_123" or just "123"

        Returns:
            JSON object confirming deletion with deleted status, id, and current_time
        """
        logger.info(f"=== delete_task called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Delete task
            response = api_client._make_request("DELETE", f"/todos/{todo_id}")
            logger.info(
                f"delete_todo response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to delete task: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Deleted task {task_id}")
            return json.dumps(
                {
                    "id": task_id,
                    "status": "deleted",
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in delete_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def complete_task(task_id: str) -> str:
        """
        Mark a task as completed.

        Sets the task status to "completed" and records the completion timestamp.
        This is a convenience method equivalent to update_task with status="completed".

        Args:
            task_id: Task ID to complete - format "task_123" or just "123"

        Returns:
            JSON object confirming completion with status, id, and current_time
        """
        logger.info(f"=== complete_task called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Complete task using dedicated endpoint
            response = api_client._make_request("POST", f"/todos/{todo_id}/complete")
            logger.info(
                f"complete_todo response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to complete task: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Completed task {task_id}")
            return json.dumps(
                {
                    "id": task_id,
                    "status": "completed",
                    "current_time": datetime.datetime.now().isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in complete_task: {e}", exc_info=True)
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
