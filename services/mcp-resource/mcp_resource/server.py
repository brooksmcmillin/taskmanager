import datetime
import json
import logging
import os
from functools import partial
from typing import Any
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp_auth_framework.cors import build_cors_headers, parse_allowed_origins
from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.middleware import NormalizePathMiddleware
from mcp_resource_framework.oauth_discovery import register_oauth_discovery_endpoints
from mcp_resource_framework.security import guard_tool
from mcp_resource_framework.validation import validate_dict_response, validate_list_response
from pydantic import AnyHttpUrl
from taskmanager_sdk import VALID_DEADLINE_TYPES, TaskManagerClient

logger = logging.getLogger(__name__)


def _past_due_date_warning(due_date: str | None) -> str | None:
    """Return a warning string if due_date is in the past, else None."""
    if not due_date:
        return None
    try:
        parsed = datetime.date.fromisoformat(due_date)
        if parsed < datetime.datetime.now(tz=datetime.UTC).date():
            return f"Due date {due_date} is in the past"
    except ValueError:
        pass
    return None


DEFAULT_SCOPE = ["read"]

load_dotenv()
# OAuth client credentials (for MCP OAuth flow)
CLIENT_ID = os.environ["TASKMANAGER_CLIENT_ID"]
CLIENT_SECRET = os.environ["TASKMANAGER_CLIENT_SECRET"]
MCP_AUTH_SERVER = os.environ["MCP_AUTH_SERVER"]

# TaskManager API URL
TASKMANAGER_URL = os.environ.get("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")

# API key for TaskManager API access (replaces username/password auth)
API_KEY = os.environ.get("TASKMANAGER_API_KEY")

ALLOWED_MCP_ORIGINS = parse_allowed_origins()


def get_api_client() -> TaskManagerClient:
    """Get API client for authenticated user.

    Uses an API key for authentication. The API key should be set
    via the TASKMANAGER_API_KEY environment variable.

    Returns:
        TaskManagerClient: Authenticated API client

    Raises:
        RuntimeError: If TASKMANAGER_API_KEY is not configured
        NetworkError: If unable to connect to backend
    """
    if not API_KEY:
        raise RuntimeError(
            "TASKMANAGER_API_KEY environment variable is not set. "
            "Please generate an API key in the TaskManager settings."
        )

    # Use the public TaskManager URL for API calls
    # Pass API key as access_token - SDK will use it as Bearer token
    task_manager = TaskManagerClient(
        base_url=f"{TASKMANAGER_URL}/api",
        access_token=API_KEY,
    )
    logger.debug("Created TaskManager API client with API key authentication")
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

    # Register all OAuth 2.0 discovery endpoints (RFC 9908, RFC 8414, OIDC)
    register_oauth_discovery_endpoints(
        app,
        server_url=str(server_url),
        auth_server_public_url=str(auth_server_public_url),
        scopes=DEFAULT_SCOPE,
        cors_header_builder=partial(build_cors_headers, allowed_origins=ALLOWED_MCP_ORIGINS),
        resource_documentation=f"{str(server_url).rstrip('/')}/docs",
    )

    # -----------------------------------------------------------------------
    # MCP Resources (read-only lookups, no @guard_tool needed)
    # -----------------------------------------------------------------------

    @app.resource("taskmanager://health")
    async def resource_health() -> str:
        """Backend health check with per-subsystem status."""
        api_client = get_api_client()
        response = api_client.health_check()
        data, error = validate_dict_response(response, "health")
        if error:
            return json.dumps({"error": error})
        return json.dumps(data)

    @app.resource("taskmanager://categories")
    async def resource_categories() -> str:
        """List all task categories with the count of tasks in each."""
        api_client = get_api_client()
        response = api_client.get_categories()
        categories, error = validate_list_response(response, "categories")
        if error:
            return json.dumps({"error": error})
        return json.dumps({"categories": categories})

    @app.resource("taskmanager://snippets/categories")
    async def resource_snippet_categories() -> str:
        """List all snippet categories with the count of snippets in each."""
        api_client = get_api_client()
        response = api_client.get_snippet_categories()
        categories, error = validate_list_response(response, "categories", key="data")
        if error:
            return json.dumps({"error": error})
        return json.dumps({"categories": categories})

    @app.resource("taskmanager://wiki/pages")
    async def resource_wiki_pages() -> str:
        """List all wiki pages (id, title, slug, timestamps)."""
        api_client = get_api_client()
        response = api_client.list_wiki_pages()
        pages, error = validate_list_response(response, "wiki pages", key="data")
        if error:
            return json.dumps({"error": error})
        return json.dumps({"pages": pages, "count": len(pages)})

    # -----------------------------------------------------------------------
    # MCP Tools
    # -----------------------------------------------------------------------

    @app.tool()
    @guard_tool(input_params=["status", "category"], screen_output=True)
    async def get_tasks(
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        category: str | None = None,
        deadline_type: str | None = None,
        limit: int | None = None,
        include_subtasks: bool = True,
        order_by: str | None = None,
    ) -> str:
        """
        Retrieve tasks with filtering options.

        Args:
            status: Filter by status - one of "pending", "in_progress", "completed", "cancelled", "overdue", or "all"
            start_date: Filter tasks with due date on or after this date (ISO format, e.g., "2025-12-14")
            end_date: Filter tasks with due date on or before this date (ISO format, e.g., "2025-12-20")
            category: Filter by category/project name
            deadline_type: Filter by deadline type - one of "flexible", "preferred", "firm", "hard"
            limit: Maximum number of tasks to return
            include_subtasks: Whether to include subtasks in the response (default: True)
            order_by: Sort order - one of "position", "due_date", "deadline_type"

        Returns:
            JSON object with "tasks" array containing task objects with fields:
            id, title, description, due_date, deadline_type, status, category, priority, tags, parent_id, subtasks, created_at, updated_at
        """
        logger.info(
            f"=== get_tasks called: status={status}, start_date={start_date}, "
            f"end_date={end_date}, category={category}, limit={limit}, include_subtasks={include_subtasks} ==="
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
                deadline_type=deadline_type,
                limit=limit,
                include_subtasks=include_subtasks,
                order_by=order_by,
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
                        "deadline_type": task.get("deadline_type", "preferred"),
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
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
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
        deadline_type: str = "preferred",
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
            deadline_type: How strict the due date is - one of "flexible" (reschedule freely),
                          "preferred" (soft target, default), "firm" (avoid moving),
                          "hard" (never reschedule)
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
            # Validate deadline_type
            if deadline_type not in VALID_DEADLINE_TYPES:
                return json.dumps(
                    {
                        "error": f"Invalid deadline_type: {deadline_type!r}. "
                        f"Must be one of: {', '.join(VALID_DEADLINE_TYPES)}"
                    }
                )

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

            # Use SDK method with parent_id support
            response = api_client.create_todo(
                title=title,
                description=description,
                category=category,
                priority=priority,
                due_date=due_date,
                deadline_type=deadline_type,
                tags=tags,
                parent_id=parent_id_int,
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

            # Include the resolved category in the response so callers can confirm
            # what project was matched or auto-created when a category was requested.
            resolved_category = task.get("project_name") if task is not None else None

            result: dict[str, Any] = {
                "id": f"task_{task_id}",
                "title": task.get("title", title) if task is not None else title,
                "status": "created",
                "category": resolved_category,
                "parent_id": f"task_{parent_id_int}" if parent_id_int else None,
                "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            }
            warning = _past_due_date_warning(due_date)
            if warning:
                result["warning"] = warning
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in create_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(screen_output=True)
    async def create_tasks(
        tasks: list[dict[str, Any]],
        skip_duplicates: bool = True,
        wiki_page_id: int | None = None,
    ) -> str:
        """
        Create multiple tasks in a single request (batch creation).

        More efficient than calling create_task multiple times—sends one
        API request instead of N sequential calls.

        Supports inline parent-child relationships: use ``parent_index``
        (0-based) to reference another task in the same batch as the parent.
        Parents must appear before children in the list, and only one level
        of nesting is allowed.  ``parent_index`` and ``parent_id`` are
        mutually exclusive per task.

        Args:
            tasks: Array of task objects. Each object supports:
                - title (required): Task title
                - description (optional): Task details
                - due_date (optional): Due date "YYYY-MM-DD"
                - deadline_type (optional): "flexible", "preferred", "firm", or "hard"
                - category (optional): Project/category name
                - priority (optional): "low", "medium", "high", or "urgent"
                - tags (optional): List of tags
                - parent_id (optional): Parent task ID ("task_123" or "123")
                  for existing tasks
                - parent_index (optional): 0-based index of another task in
                  this batch to use as parent. Mutually exclusive with
                  parent_id.
                - estimated_hours (optional): Estimated hours to complete
                - depends_on (optional): List of 0-based indices of other tasks
                  in this batch that must be completed before this task.
                  Example: [0, 1] means this task depends on the first and
                  second tasks in the batch.
            skip_duplicates: If true (default), silently skip tasks whose title
                matches an existing active task instead of failing the entire
                batch. Set to false to reject the batch on any duplicate.
            wiki_page_id: Optional wiki page ID to auto-link to all created tasks.
                When provided, every task created in this batch is automatically
                linked to the specified wiki page, eliminating the need for
                separate link_wiki_page_to_task calls.

        Returns:
            JSON object with created task IDs and count
        """
        try:
            if not tasks:
                return json.dumps({"error": "tasks array must not be empty"})
            if len(tasks) > 50:
                return json.dumps({"error": "Maximum 50 tasks per batch"})

            # Validate and transform each task
            todo_dicts: list[dict[str, Any]] = []
            for i, task in enumerate(tasks):
                if not isinstance(task, dict):
                    return json.dumps({"error": f"Task at index {i} must be an object"})
                title = task.get("title")
                if not title:
                    return json.dumps({"error": f"Task at index {i} is missing required 'title'"})

                deadline_type = task.get("deadline_type", "preferred")
                if deadline_type not in VALID_DEADLINE_TYPES:
                    return json.dumps(
                        {
                            "error": f"Task at index {i}: invalid deadline_type "
                            f"{deadline_type!r}. "
                            f"Must be one of: {', '.join(VALID_DEADLINE_TYPES)}"
                        }
                    )

                todo: dict[str, Any] = {"title": title}
                if task.get("description"):
                    todo["description"] = task["description"]
                if task.get("category"):
                    todo["category"] = task["category"]
                if task.get("priority"):
                    todo["priority"] = task["priority"]
                if task.get("due_date"):
                    todo["due_date"] = task["due_date"]
                if deadline_type != "preferred":
                    todo["deadline_type"] = deadline_type
                if task.get("tags"):
                    todo["tags"] = task["tags"]
                if task.get("estimated_hours") is not None:
                    todo["estimated_hours"] = task["estimated_hours"]

                parent_id = task.get("parent_id")
                parent_index = task.get("parent_index")

                if parent_id is not None and parent_index is not None:
                    return json.dumps(
                        {
                            "error": f"Task at index {i}: cannot specify both "
                            f"parent_id and parent_index"
                        }
                    )

                if parent_id is not None:
                    pid_str = str(parent_id)
                    numeric_id = (
                        pid_str.replace("task_", "") if pid_str.startswith("task_") else pid_str
                    )
                    try:
                        todo["parent_id"] = int(numeric_id)
                    except ValueError:
                        return json.dumps(
                            {"error": f"Task at index {i}: invalid parent_id format: {parent_id}"}
                        )

                if parent_index is not None:
                    if not isinstance(parent_index, int):
                        return json.dumps(
                            {"error": f"Task at index {i}: parent_index must be an integer"}
                        )
                    todo["parent_index"] = parent_index

                depends_on = task.get("depends_on")
                if depends_on is not None:
                    if not isinstance(depends_on, list):
                        return json.dumps(
                            {"error": f"Task at index {i}: depends_on must be a list of integers"}
                        )
                    todo["depends_on"] = depends_on

                todo_dicts.append(todo)

            api_client = get_api_client()
            response = api_client.batch_create_todos(
                todo_dicts,
                skip_duplicates=skip_duplicates,
                wiki_page_id=wiki_page_id,
            )

            created_tasks, list_error = validate_list_response(response, "batch created tasks")
            if list_error:
                return json.dumps({"error": list_error})

            results: list[dict[str, Any]] = []
            warnings: list[str] = []
            for task_data in created_tasks or []:
                task_id = task_data.get("id")
                result_item: dict[str, Any] = {
                    "id": f"task_{task_id}" if task_id else None,
                    "title": task_data.get("title", ""),
                    # Include the resolved category so callers can confirm what
                    # project was matched or auto-created for each task.
                    "category": task_data.get("project_name"),
                }
                if task_data.get("parent_id"):
                    result_item["parent_id"] = f"task_{task_data['parent_id']}"
                results.append(result_item)
                warning = _past_due_date_warning(task_data.get("due_date"))
                if warning:
                    warnings.append(f"task_{task_id}: {warning}")

            result: dict[str, Any] = {
                "created": results,
                "count": len(results),
                "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            }
            # Propagate skipped_duplicates count from the API response
            meta = response.data.get("meta", {}) if isinstance(response.data, dict) else {}
            skipped = meta.get("skipped_duplicates", 0)
            if skipped:
                result["skipped_duplicates"] = skipped
            if wiki_page_id is not None:
                result["wiki_page_id"] = wiki_page_id
                result["wiki_links_created"] = len(results)
            if warnings:
                result["warnings"] = warnings
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in create_tasks: {e}", exc_info=True)
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
        deadline_type: str | None = None,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        parent_id: str | None = None,
        estimated_hours: float | None = None,
    ) -> str:
        """
        Update an existing task.

        Args:
            task_id: Task ID (required) - format "task_123" or just "123"
            title: New title (optional)
            description: New description (optional)
            due_date: New due date in ISO format for rescheduling (optional)
            deadline_type: How strict the due date is - one of "flexible" (reschedule freely),
                          "preferred" (soft target), "firm" (avoid moving),
                          "hard" (never reschedule) (optional)
            status: New status - one of "pending", "in_progress", "completed", "cancelled" (optional)
            category: New category/project name (optional)
            priority: New priority - one of "low", "medium", "high", "urgent" (optional)
            tags: New list of tags (optional)
            parent_id: New parent task ID to move task - format "task_123" or just "123" (optional)
            estimated_hours: Estimated hours to complete (optional)

        Returns:
            JSON object with id, updated_fields list, and status confirming update
        """
        logger.info(f"=== update_task called: task_id='{task_id}', parent_id={parent_id} ===")
        try:
            # Validate deadline_type if provided
            if deadline_type is not None and deadline_type not in VALID_DEADLINE_TYPES:
                return json.dumps(
                    {
                        "error": f"Invalid deadline_type: {deadline_type!r}. "
                        f"Must be one of: {', '.join(VALID_DEADLINE_TYPES)}"
                    }
                )

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
            if deadline_type is not None:
                updated_fields.append("deadline_type")
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
            if estimated_hours is not None:
                updated_fields.append("estimated_hours")

            # Use SDK method with parent_id support
            response = api_client.update_todo(
                todo_id=todo_id,
                title=title,
                description=description,
                category=category,
                priority=priority,
                estimated_hours=estimated_hours,
                status=status,
                due_date=due_date,
                deadline_type=deadline_type,
                tags=tags,
                parent_id=parent_id_int,
            )
            logger.info(
                f"update_todo response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to update task: {response.error}")
                return json.dumps({"error": response.error})

            # Return response in expected format
            result: dict[str, Any] = {
                "id": f"task_{todo_id}",
                "updated_fields": updated_fields,
                "status": "updated",
                "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            }
            warning = _past_due_date_warning(due_date)
            if warning:
                result["warning"] = warning
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in update_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["name", "description"], screen_output=True)
    async def create_project(
        name: str,
        description: str | None = None,
        color: str | None = None,
        show_on_calendar: bool | None = None,
    ) -> str:
        """
        Create a new project for organizing tasks.

        Projects group related tasks together and appear as categories.
        Use this to set up organizational structure before creating tasks.

        Args:
            name: Project name (required)
            description: Project description (optional)
            color: Project color in hex format, e.g., "#FF5733" (optional)
            show_on_calendar: Whether to show this project's tasks on calendar
                and home dashboard. Set to false for agent-only or background
                projects. (optional, default: true)

        Returns:
            JSON object with id, name, and status fields confirming project creation
        """
        logger.info(f"=== create_project called: name='{name}', color={color} ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            response = api_client.create_project(
                name=name,
                description=description,
                color=color,
                show_on_calendar=show_on_calendar,
            )
            logger.info(
                f"create_project response: success={response.success}, status={response.status_code}"
            )

            project, project_error = validate_dict_response(response, "created project")
            if project_error:
                logger.error(f"Failed to create project: {project_error}")
                return json.dumps({"error": project_error})

            logger.info(f"Created project: {project}")

            project_id = project.get("id") if project is not None else None
            if project_id is None:
                logger.warning("Project data missing 'id' field")
                return json.dumps({"error": "Created project has no ID"})

            result = {
                "id": project_id,
                "name": project.get("name", name) if project is not None else name,
                "status": "created",
                "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"Exception in create_project: {e}", exc_info=True)
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
                        "deadline_type": task.get("deadline_type", "preferred"),
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
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
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

            # Get attachments using SDK method
            response = api_client.get_attachments(todo_id)
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
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_task_attachments: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def list_task_comments(task_id: str) -> str:
        """
        List all comments for a specific task.

        Args:
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object with "comments" array containing comment objects with fields:
            id, todo_id, user_id, content, created_at, updated_at
        """
        logger.info(f"=== list_task_comments called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()

            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            response = api_client.get_comments(todo_id)
            logger.info(
                f"list_comments response: success={response.success}, status={response.status_code}"
            )

            comments, comments_error = validate_list_response(response, "comments")
            if comments_error:
                logger.error(f"Failed to get comments: {comments_error}")
                return json.dumps({"error": comments_error})

            logger.info(f"Returning {len(comments)} comments")
            return json.dumps(
                {
                    "task_id": task_id,
                    "comments": comments,
                    "count": len(comments),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_task_comments: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["content"], screen_output=True)
    async def add_task_comment(task_id: str, content: str) -> str:
        """
        Add a comment to a task.

        Args:
            task_id: Task ID - format "task_123" or just "123"
            content: Comment text content (required)

        Returns:
            JSON object confirming comment creation with id, content, and status
        """
        logger.info(f"=== add_task_comment called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()

            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            response = api_client.create_comment(todo_id, content)
            logger.info(
                f"create_comment response: success={response.success}, status={response.status_code}"
            )

            comment, comment_error = validate_dict_response(response, "created comment")
            if comment_error:
                logger.error(f"Failed to create comment: {comment_error}")
                return json.dumps({"error": comment_error})

            logger.info(f"Created comment: {comment}")
            comment_id = comment.get("id") if comment is not None else None
            return json.dumps(
                {
                    "task_id": task_id,
                    "comment_id": comment_id,
                    "content": content,
                    "status": "created",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in add_task_comment: {e}", exc_info=True)
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

            # Get task details using SDK method
            response = api_client.get_todo(todo_id)
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
                "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
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

            # Delete task using SDK method
            response = api_client.delete_todo(todo_id)
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
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in delete_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["status", "category"], screen_output=True)
    async def get_agent_tasks(
        due_today: bool = False,
        agent_actionable_only: bool = False,
        unclassified_only: bool = False,
        include_subtasks: bool = True,
    ) -> str:
        """
        Get tasks filtered for AI agent processing.

        Convenience method that pre-filters tasks for agent work queues.
        Use this instead of get_tasks when working as an AI agent.

        Args:
            due_today: Only return tasks due today (default: False)
            agent_actionable_only: Only return tasks the agent can work on autonomously (default: False)
            unclassified_only: Only return tasks that haven't been classified yet (default: False)
            include_subtasks: Whether to include subtasks in the response (default: True)

        Returns:
            JSON object with "tasks" array containing task objects with agent fields:
            id, title, description, due_date, status, category, priority, tags,
            agent_actionable, action_type, autonomy_tier, agent_status, agent_notes, blocking_reason
        """
        logger.info(
            f"=== get_agent_tasks called: due_today={due_today}, "
            f"agent_actionable_only={agent_actionable_only}, "
            f"unclassified_only={unclassified_only} ==="
        )
        try:
            api_client = get_api_client()

            # Build date filter for today if requested
            start_date = None
            end_date = None
            if due_today:
                today = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d")
                start_date = today
                end_date = today

            # Get all pending/in_progress tasks
            response = api_client.get_todos(
                status="pending",
                start_date=start_date,
                end_date=end_date,
                include_subtasks=include_subtasks,
            )

            tasks, tasks_error = validate_list_response(response, "tasks")
            if tasks_error:
                logger.error(f"Failed to get tasks: {tasks_error}")
                return json.dumps({"error": tasks_error})

            # Filter based on agent criteria
            result_tasks = []
            for task in tasks:
                task_id = task.get("id")
                if task_id is None:
                    continue

                agent_actionable = task.get("agent_actionable")
                action_type = task.get("action_type")

                # Apply filters
                if agent_actionable_only and agent_actionable is not True:
                    continue
                if unclassified_only and (agent_actionable is not None or action_type is not None):
                    continue

                # Transform subtasks
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
                                "agent_actionable": subtask.get("agent_actionable"),
                                "action_type": subtask.get("action_type"),
                                "autonomy_tier": subtask.get("autonomy_tier"),
                                "agent_status": subtask.get("agent_status"),
                            }
                        )

                result_tasks.append(
                    {
                        "id": f"task_{task_id}",
                        "title": task.get("title", ""),
                        "description": task.get("description"),
                        "due_date": task.get("due_date"),
                        "deadline_type": task.get("deadline_type", "preferred"),
                        "status": task.get("status", "pending"),
                        "category": task.get("project_name") or task.get("category"),
                        "priority": task.get("priority", "medium"),
                        "tags": task.get("tags") or [],
                        "subtasks": subtasks_list,
                        "agent_actionable": agent_actionable,
                        "action_type": action_type,
                        "autonomy_tier": task.get("autonomy_tier"),
                        "agent_status": task.get("agent_status"),
                        "agent_notes": task.get("agent_notes"),
                        "blocking_reason": task.get("blocking_reason"),
                        "created_at": task.get("created_at"),
                        "updated_at": task.get("updated_at"),
                    }
                )

            logger.info(f"Returning {len(result_tasks)} agent tasks")
            return json.dumps(
                {
                    "tasks": result_tasks,
                    "count": len(result_tasks),
                    "filters_applied": {
                        "due_today": due_today,
                        "agent_actionable_only": agent_actionable_only,
                        "unclassified_only": unclassified_only,
                    },
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_agent_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["action_type", "blocking_reason"], screen_output=True)
    async def classify_task(
        task_id: str,
        action_type: str,
        agent_actionable: bool,
        autonomy_tier: int | None = None,
        blocking_reason: str | None = None,
    ) -> str:
        """
        Classify a task with action type, autonomy tier, and agent actionability.

        Use this to classify tasks that weren't automatically classified at creation.
        The agent should analyze the task title/description and determine:
        1. What type of action is required
        2. What autonomy tier (risk level) applies
        3. Whether the agent can complete it autonomously

        Args:
            task_id: Task ID - format "task_123" or just "123"
            action_type: Type of action - one of "research", "code", "email", "document",
                        "purchase", "schedule", "call", "errand", "manual", "review",
                        "data_entry", "other"
            agent_actionable: True if agent can complete without human intervention
            autonomy_tier: Risk level 1-4 (1=fully autonomous, 2=propose & execute,
                          3=propose & wait, 4=never autonomous). If not provided,
                          a default is inferred from action_type.
            blocking_reason: Why agent can't proceed (optional, use if agent_actionable=False)

        Returns:
            JSON object confirming classification with updated task fields
        """
        logger.info(
            f"=== classify_task called: task_id={task_id}, "
            f"action_type={action_type}, autonomy_tier={autonomy_tier}, "
            f"agent_actionable={agent_actionable} ==="
        )
        try:
            api_client = get_api_client()

            # Extract numeric ID
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Validate action_type
            valid_action_types = [
                "research",
                "code",
                "email",
                "document",
                "purchase",
                "schedule",
                "call",
                "errand",
                "manual",
                "review",
                "data_entry",
                "other",
            ]
            if action_type not in valid_action_types:
                return json.dumps(
                    {
                        "error": f"Invalid action_type: {action_type}. Must be one of: {valid_action_types}"
                    }
                )

            # Validate autonomy_tier if provided
            if autonomy_tier is not None:
                if not isinstance(autonomy_tier, int):
                    return json.dumps({"error": "autonomy_tier must be an integer"})
                if autonomy_tier < 1 or autonomy_tier > 4:
                    return json.dumps(
                        {"error": f"Invalid autonomy_tier: {autonomy_tier}. Must be 1-4."}
                    )

            # Infer default autonomy_tier from action_type if not provided
            # NOTE: This mapping is duplicated from services/backend/app/models/todo.py
            # (ACTION_TYPE_DEFAULT_TIER). Keep in sync if changing defaults.
            if autonomy_tier is None:
                default_tiers = {
                    "research": 1,
                    "review": 1,
                    "data_entry": 2,
                    "document": 2,
                    "email": 2,
                    "schedule": 2,
                    "code": 3,
                    "purchase": 4,
                    "call": 4,
                    "errand": 4,
                    "manual": 4,
                    "other": 3,
                }
                autonomy_tier = default_tiers.get(action_type, 3)

            # Update task with classification
            response = api_client.update_todo(
                todo_id=todo_id,
                action_type=action_type,
                agent_actionable=agent_actionable,
                autonomy_tier=autonomy_tier,
                blocking_reason=blocking_reason,
            )

            if not response.success:
                logger.error(f"Failed to classify task: {response.error}")
                return json.dumps({"error": response.error})

            return json.dumps(
                {
                    "id": f"task_{todo_id}",
                    "status": "classified",
                    "action_type": action_type,
                    "autonomy_tier": autonomy_tier,
                    "agent_actionable": agent_actionable,
                    "blocking_reason": blocking_reason,
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in classify_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["note"], screen_output=True)
    async def add_agent_note(task_id: str, note: str, append: bool = True) -> str:
        """
        Add an agent note to a task.

        Use this to store research findings, context, or other information
        the agent has gathered while working on a task. Notes persist and
        can be used by future agent sessions.

        Args:
            task_id: Task ID - format "task_123" or just "123"
            note: The note content to add
            append: If True, append to existing notes. If False, replace (default: True)

        Returns:
            JSON object confirming note was added
        """
        logger.info(f"=== add_agent_note called: task_id={task_id}, append={append} ===")
        try:
            api_client = get_api_client()

            # Extract numeric ID
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Get current task to append notes if needed
            if append:
                task_response = api_client.get_todo(todo_id)
                if task_response.success and task_response.data:
                    existing_notes = task_response.data.get("agent_notes") or ""
                    if existing_notes:
                        timestamp = datetime.datetime.now(tz=datetime.UTC).strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        note = f"{existing_notes}\n\n---\n[{timestamp}]\n{note}"

            # Update task with note
            response = api_client.update_todo(
                todo_id=todo_id,
                agent_notes=note,
            )

            if not response.success:
                logger.error(f"Failed to add note: {response.error}")
                return json.dumps({"error": response.error})

            return json.dumps(
                {
                    "id": f"task_{todo_id}",
                    "status": "note_added",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in add_agent_note: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["status", "blocking_reason"], screen_output=True)
    async def set_agent_status(
        task_id: str,
        status: str,
        blocking_reason: str | None = None,
    ) -> str:
        """
        Set the agent processing status for a task.

        Use this to track agent progress on tasks. Helps coordinate
        between multiple agent sessions and provides visibility to users.

        Args:
            task_id: Task ID - format "task_123" or just "123"
            status: Agent status - one of "pending_review", "in_progress",
                   "completed", "blocked", "needs_human"
            blocking_reason: Required when status is "blocked" - explain why

        Returns:
            JSON object confirming status update
        """
        logger.info(f"=== set_agent_status called: task_id={task_id}, status={status} ===")
        try:
            api_client = get_api_client()

            # Extract numeric ID
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            # Validate status
            valid_statuses = [
                "pending_review",
                "in_progress",
                "completed",
                "blocked",
                "needs_human",
            ]
            if status not in valid_statuses:
                return json.dumps(
                    {"error": f"Invalid status: {status}. Must be one of: {valid_statuses}"}
                )

            # Require blocking_reason for blocked status
            if status == "blocked" and not blocking_reason:
                return json.dumps({"error": "blocking_reason is required when status is 'blocked'"})

            # Update task with agent status
            response = api_client.update_todo(
                todo_id=todo_id,
                agent_status=status,
                blocking_reason=blocking_reason if status == "blocked" else None,
            )

            if not response.success:
                logger.error(f"Failed to set agent status: {response.error}")
                return json.dumps({"error": response.error})

            return json.dumps(
                {
                    "id": f"task_{todo_id}",
                    "agent_status": status,
                    "blocking_reason": blocking_reason if status == "blocked" else None,
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in set_agent_status: {e}", exc_info=True)
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

            # Complete task using SDK method
            response = api_client.complete_todo(todo_id)
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
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in complete_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def list_dependencies(task_id: str) -> str:
        """
        List all dependencies for a task (tasks it depends on).

        Returns tasks that must be completed before this task can start.

        Args:
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object with "dependencies" array containing dependency task objects
            with fields: id, title, status, priority, due_date, project_id, project_name
        """
        logger.info(f"=== list_dependencies called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric ID from task_id
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            response = api_client.get_dependencies(todo_id)
            logger.info(
                f"get_dependencies response: success={response.success}, status={response.status_code}"
            )

            dependencies, dep_error = validate_list_response(response, "dependencies")
            if dep_error:
                logger.error(f"Failed to get dependencies: {dep_error}")
                return json.dumps({"error": dep_error})

            # Transform dependency IDs to task_N format
            result_deps = []
            for dep in dependencies:
                dep_id = dep.get("id")
                if dep_id is None:
                    continue
                result_deps.append(
                    {
                        "id": f"task_{dep_id}",
                        "title": dep.get("title", ""),
                        "status": dep.get("status", "pending"),
                        "priority": dep.get("priority", "medium"),
                        "due_date": dep.get("due_date"),
                        "project_name": dep.get("project_name"),
                    }
                )

            logger.info(f"Returning {len(result_deps)} dependencies for task {task_id}")
            return json.dumps(
                {
                    "task_id": task_id,
                    "dependencies": result_deps,
                    "count": len(result_deps),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_dependencies: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def add_dependency(task_id: str, dependency_id: str) -> str:
        """
        Add a dependency to a task.

        Declares that the task identified by dependency_id must be completed
        before the task identified by task_id can start. Prevents circular
        dependencies and self-dependencies.

        Args:
            task_id: The dependent task ID - format "task_123" or just "123"
            dependency_id: The task this depends on - format "task_123" or just "123"

        Returns:
            JSON object confirming the dependency was created
        """
        logger.info(
            f"=== add_dependency called: task_id='{task_id}', dependency_id='{dependency_id}' ==="
        )
        try:
            api_client = get_api_client()
            logger.debug("API client created successfully")

            # Extract numeric IDs
            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            dep_numeric_id = (
                dependency_id.replace("task_", "")
                if dependency_id.startswith("task_")
                else dependency_id
            )
            try:
                dep_id = int(dep_numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid dependency_id format: {dependency_id}"})

            response = api_client.add_dependency(todo_id, dep_id)
            logger.info(
                f"add_dependency response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to add dependency: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Added dependency: task {task_id} depends on {dependency_id}")
            return json.dumps(
                {
                    "task_id": task_id,
                    "dependency_id": dependency_id,
                    "status": "created",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in add_dependency: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    # -----------------------------------------------------------------------
    # Wiki tools
    # -----------------------------------------------------------------------

    @app.tool()
    @guard_tool(input_params=["q"], screen_output=True)
    async def search_wiki_pages(q: str) -> str:
        """
        Search wiki pages by title or content.

        For a full listing of all pages without filtering, use the
        ``taskmanager://wiki/pages`` resource instead.

        Args:
            q: Search query to filter pages by title or content (required)

        Returns:
            JSON object with "pages" array containing wiki page summaries
            with fields: id, title, slug, created_at, updated_at
        """
        logger.info(f"=== search_wiki_pages called: q={q} ===")
        try:
            api_client = get_api_client()
            response = api_client.list_wiki_pages(q=q)
            logger.info(
                f"search_wiki_pages response: success={response.success}, status={response.status_code}"
            )

            pages, pages_error = validate_list_response(response, "wiki pages", key="data")
            if pages_error:
                logger.error(f"Failed to list wiki pages: {pages_error}")
                return json.dumps({"error": pages_error})

            logger.info(f"Returning {len(pages)} wiki pages")
            return json.dumps(
                {
                    "pages": pages,
                    "count": len(pages),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in search_wiki_pages: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["title", "content"], screen_output=True)
    async def create_wiki_page(
        title: str,
        content: str = "",
        slug: str | None = None,
        parent_id: int | None = None,
    ) -> str:
        """
        Create a new wiki page.

        Args:
            title: Page title (required, 1-500 characters)
            content: Page content in markdown format (optional, default: "")
            slug: URL-friendly slug (optional, auto-generated from title if not provided).
                  Must be lowercase letters, numbers, and hyphens only.
            parent_id: Parent page ID to nest this page under (optional).
                       Creates a hierarchical page structure. Max depth is 3 levels.

        Returns:
            JSON object with created page data including id, title, slug, content,
            created_at, and updated_at
        """
        logger.info(f"=== create_wiki_page called: title='{title}', slug={slug}, parent_id={parent_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.create_wiki_page(title=title, content=content, slug=slug, parent_id=parent_id)
            logger.info(
                f"create_wiki_page response: success={response.success}, status={response.status_code}"
            )

            page, page_error = validate_dict_response(response, "created wiki page")
            if page_error:
                logger.error(f"Failed to create wiki page: {page_error}")
                return json.dumps({"error": page_error})

            logger.info(f"Created wiki page: {page}")
            return json.dumps(
                {
                    "page": page,
                    "status": "created",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in create_wiki_page: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_wiki_page(slug_or_id: str) -> str:
        """
        Get a wiki page by its slug or numeric ID.

        Args:
            slug_or_id: Page slug (e.g., "meeting-notes") or numeric ID (e.g., "42")

        Returns:
            JSON object with full page data including id, title, slug, content,
            created_at, and updated_at
        """
        logger.info(f"=== get_wiki_page called: slug_or_id='{slug_or_id}' ===")
        try:
            api_client = get_api_client()
            response = api_client.get_wiki_page(slug_or_id)
            logger.info(
                f"get_wiki_page response: success={response.success}, status={response.status_code}"
            )

            page, page_error = validate_dict_response(response, "wiki page")
            if page_error:
                logger.error(f"Failed to get wiki page: {page_error}")
                return json.dumps({"error": page_error})

            logger.info(f"Retrieved wiki page: id={page.get('id') if page else None}")
            return json.dumps(
                {
                    "page": page,
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_wiki_page: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["title", "content"], screen_output=True)
    async def update_wiki_page(
        page_id: int,
        title: str | None = None,
        content: str | None = None,
        slug: str | None = None,
        append: bool = False,
        parent_id: int | None = None,
        remove_parent: bool = False,
    ) -> str:
        """
        Update an existing wiki page.

        Args:
            page_id: Wiki page ID to update
            title: New page title (optional, 1-500 characters)
            content: New page content in markdown format (optional)
            slug: New URL-friendly slug (optional). Must be lowercase letters,
                  numbers, and hyphens only.
            append: If True, append content to the existing page content instead
                    of replacing it. Useful for adding notes or log entries to a
                    page without overwriting existing content. Default: False.
            parent_id: New parent page ID to move this page under (optional).
                       Max depth is 3 levels.
            remove_parent: If True, remove the parent and make this a root page.
                           Mutually exclusive with parent_id. Default: False.

        Returns:
            JSON object with updated page data including id, title, slug, content,
            revision_number, created_at, and updated_at
        """
        logger.info(
            f"=== update_wiki_page called: page_id={page_id}, title={title}, slug={slug}, append={append}, parent_id={parent_id}, remove_parent={remove_parent} ==="
        )
        if parent_id is not None and remove_parent:
            return json.dumps({"error": "parent_id and remove_parent are mutually exclusive"})
        try:
            api_client = get_api_client()
            response = api_client.update_wiki_page(
                page_id=page_id, title=title, content=content, slug=slug, append=append,
                parent_id=parent_id, remove_parent=remove_parent,
            )
            logger.info(
                f"update_wiki_page response: success={response.success}, status={response.status_code}"
            )

            page, page_error = validate_dict_response(response, "updated wiki page")
            if page_error:
                logger.error(f"Failed to update wiki page: {page_error}")
                return json.dumps({"error": page_error})

            logger.info(f"Updated wiki page: {page}")
            return json.dumps(
                {
                    "page": page,
                    "status": "updated",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in update_wiki_page: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def delete_wiki_page(page_id: int) -> str:
        """
        Soft-delete a wiki page.

        The page will no longer appear in listings or be fetchable, but its
        data and revision history are preserved internally.

        Args:
            page_id: Wiki page ID to delete

        Returns:
            JSON object confirming deletion with deleted status and page id
        """
        logger.info(f"=== delete_wiki_page called: page_id={page_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.delete_wiki_page(page_id)
            logger.info(
                f"delete_wiki_page response: success={response.success}, status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to delete wiki page: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Deleted wiki page {page_id}")
            return json.dumps(
                {
                    "page_id": page_id,
                    "status": "deleted",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in delete_wiki_page: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def link_wiki_page_to_task(page_id: int, task_id: str) -> str:
        """
        Link a wiki page to a task.

        Creates a bidirectional association between a wiki page and a task,
        allowing related knowledge to be connected to actionable items.

        Args:
            page_id: Wiki page ID to link
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object confirming the link with linked task summary
        """
        logger.info(
            f"=== link_wiki_page_to_task called: page_id={page_id}, task_id='{task_id}' ==="
        )
        try:
            api_client = get_api_client()

            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            response = api_client.link_wiki_page_to_task(page_id, todo_id)
            logger.info(
                f"link_wiki_page_to_task response: success={response.success}, status={response.status_code}"
            )

            task, task_error = validate_dict_response(response, "linked task")
            if task_error:
                logger.error(f"Failed to link wiki page to task: {task_error}")
                return json.dumps({"error": task_error})

            logger.info(f"Linked wiki page {page_id} to task {task_id}")
            return json.dumps(
                {
                    "page_id": page_id,
                    "task_id": task_id,
                    "linked_task": task,
                    "status": "linked",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in link_wiki_page_to_task: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_wiki_page_linked_tasks(page_id: int) -> str:
        """
        Get all tasks linked to a wiki page.

        Args:
            page_id: Wiki page ID

        Returns:
            JSON object with "tasks" array containing linked task summaries
            with fields: id, title, status, priority, due_date
        """
        logger.info(f"=== get_wiki_page_linked_tasks called: page_id={page_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.get_wiki_page_linked_tasks(page_id)
            logger.info(
                f"get_wiki_page_linked_tasks response: success={response.success}, "
                f"status={response.status_code}"
            )

            tasks, tasks_error = validate_list_response(response, "linked tasks", key="data")
            if tasks_error:
                logger.error(f"Failed to get linked tasks: {tasks_error}")
                return json.dumps({"error": tasks_error})

            # Prefix task IDs
            for task in tasks:
                if task.get("id") is not None:
                    task["id"] = f"task_{task['id']}"

            logger.info(f"Returning {len(tasks)} linked tasks for wiki page {page_id}")
            return json.dumps(
                {
                    "page_id": page_id,
                    "tasks": tasks,
                    "count": len(tasks),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_wiki_page_linked_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_task_wiki_pages(task_id: str) -> str:
        """
        Get all wiki pages linked to a task.

        Args:
            task_id: Task ID - format "task_123" or just "123"

        Returns:
            JSON object with "pages" array containing wiki page summaries
            with fields: id, title, slug, created_at, updated_at
        """
        logger.info(f"=== get_task_wiki_pages called: task_id='{task_id}' ===")
        try:
            api_client = get_api_client()

            numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
            try:
                todo_id = int(numeric_id)
            except ValueError:
                return json.dumps({"error": f"Invalid task_id format: {task_id}"})

            response = api_client.get_task_wiki_pages(todo_id)
            logger.info(
                f"get_task_wiki_pages response: success={response.success}, "
                f"status={response.status_code}"
            )

            pages, pages_error = validate_list_response(response, "wiki pages", key="data")
            if pages_error:
                logger.error(f"Failed to get task wiki pages: {pages_error}")
                return json.dumps({"error": pages_error})

            logger.info(f"Returning {len(pages)} wiki pages for task {task_id}")
            return json.dumps(
                {
                    "task_id": task_id,
                    "pages": pages,
                    "count": len(pages),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_task_wiki_pages: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def batch_link_wiki_page_to_tasks(page_id: int, task_ids: list[str]) -> str:
        """
        Link a wiki page to multiple tasks at once.

        For each task ID, the tool will attempt to create a link. The response
        reports which tasks were newly linked, which were already linked, and
        which were not found.

        Args:
            page_id: Wiki page ID
            task_ids: List of task IDs - format "task_123" or just "123"

        Returns:
            JSON object with linked, already_linked, and not_found arrays
        """
        logger.info(
            f"=== batch_link_wiki_page_to_tasks called: page_id={page_id}, task_ids={task_ids} ==="
        )
        try:
            api_client = get_api_client()

            todo_ids: list[int] = []
            invalid_ids: list[str] = []
            for tid in task_ids:
                numeric_id = tid.replace("task_", "") if tid.startswith("task_") else tid
                try:
                    todo_ids.append(int(numeric_id))
                except ValueError:
                    invalid_ids.append(tid)

            if invalid_ids:
                return json.dumps({"error": f"Invalid task_id format(s): {', '.join(invalid_ids)}"})

            response = api_client.batch_link_wiki_page_to_tasks(page_id, todo_ids)
            logger.info(
                f"batch_link_wiki_page_to_tasks response: success={response.success}, "
                f"status={response.status_code}"
            )

            result, result_error = validate_dict_response(response, "batch link result")
            if result_error:
                logger.error(f"Failed to batch link tasks: {result_error}")
                return json.dumps({"error": result_error})

            assert result is not None
            logger.info(f"Batch linked tasks to wiki page {page_id}: {result}")
            return json.dumps(
                {
                    "page_id": page_id,
                    "linked": result.get("linked", []),
                    "already_linked": result.get("already_linked", []),
                    "not_found": result.get("not_found", []),
                    "status": "completed",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in batch_link_wiki_page_to_tasks: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    # -----------------------------------------------------------------------
    # Snippet tools
    # -----------------------------------------------------------------------

    @app.tool()
    @guard_tool(input_params=["q"], screen_output=True)
    async def list_snippets(
        q: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> str:
        """
        List snippets (dated log entries), optionally filtered.

        Snippets are short, dated entries organized by category with tags.
        Use this to browse or search the user's snippet log.

        Args:
            q: Optional search query to filter by title, content, or category
            category: Optional category filter (e.g., "standup", "til")
            tag: Optional tag filter
            date_from: Optional start date filter (YYYY-MM-DD)
            date_to: Optional end date filter (YYYY-MM-DD)

        Returns:
            JSON object with "snippets" array containing snippet summaries
            with fields: id, category, title, snippet_date, tags, created_at, updated_at
        """
        logger.info(
            f"=== list_snippets called: q={q}, category={category}, "
            f"tag={tag}, date_from={date_from}, date_to={date_to} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.list_snippets(
                q=q, category=category, tag=tag, date_from=date_from, date_to=date_to
            )
            logger.info(
                f"list_snippets response: success={response.success}, status={response.status_code}"
            )

            snippets, snippets_error = validate_list_response(response, "snippets", key="data")
            if snippets_error:
                logger.error(f"Failed to list snippets: {snippets_error}")
                return json.dumps({"error": snippets_error})

            logger.info(f"Returning {len(snippets)} snippets")
            return json.dumps(
                {
                    "snippets": snippets,
                    "count": len(snippets),
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_snippets: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["category", "title", "content"], screen_output=True)
    async def create_snippet(
        category: str,
        title: str,
        content: str = "",
        snippet_date: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Create a new snippet (dated log entry).

        Snippets are short, dated entries organized by category. Use them for
        standups, TIL entries, meeting notes, decision logs, etc.

        Args:
            category: Snippet category (required, e.g., "standup", "til", "meeting")
            title: Snippet title (required, 1-500 characters)
            content: Snippet content (optional, default: "")
            snippet_date: Date for the snippet in YYYY-MM-DD format
                          (optional, defaults to today)
            tags: List of tags (optional)

        Returns:
            JSON object with created snippet data including id, category, title,
            content, snippet_date, tags, created_at
        """
        logger.info(
            f"=== create_snippet called: category='{category}', title='{title}', "
            f"snippet_date={snippet_date}, tags={tags} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.create_snippet(
                category=category,
                title=title,
                content=content,
                snippet_date=snippet_date,
                tags=tags,
            )
            logger.info(
                f"create_snippet response: success={response.success}, "
                f"status={response.status_code}"
            )

            snippet, snippet_error = validate_dict_response(response, "created snippet")
            if snippet_error:
                logger.error(f"Failed to create snippet: {snippet_error}")
                return json.dumps({"error": snippet_error})

            logger.info(f"Created snippet: id={snippet.get('id') if snippet else None}")
            return json.dumps(
                {
                    "snippet": snippet,
                    "status": "created",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in create_snippet: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_snippet(snippet_id: int) -> str:
        """
        Get a snippet by its ID.

        Args:
            snippet_id: Snippet ID

        Returns:
            JSON object with full snippet data including id, category, title,
            content, snippet_date, tags, created_at, updated_at
        """
        logger.info(f"=== get_snippet called: snippet_id={snippet_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.get_snippet(snippet_id)
            logger.info(
                f"get_snippet response: success={response.success}, status={response.status_code}"
            )

            snippet, snippet_error = validate_dict_response(response, "snippet")
            if snippet_error:
                logger.error(f"Failed to get snippet: {snippet_error}")
                return json.dumps({"error": snippet_error})

            logger.info(f"Retrieved snippet: id={snippet.get('id') if snippet else None}")
            return json.dumps(
                {
                    "snippet": snippet,
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_snippet: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["category", "title", "content"], screen_output=True)
    async def update_snippet(
        snippet_id: int,
        category: str | None = None,
        title: str | None = None,
        content: str | None = None,
        snippet_date: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """
        Update an existing snippet.

        Args:
            snippet_id: Snippet ID to update
            category: New category (optional)
            title: New title (optional, 1-500 characters)
            content: New content (optional)
            snippet_date: New date in YYYY-MM-DD format (optional)
            tags: New tags list (optional)

        Returns:
            JSON object with updated snippet data including id, category, title,
            content, snippet_date, tags, created_at, updated_at
        """
        logger.info(
            f"=== update_snippet called: snippet_id={snippet_id}, category={category}, "
            f"title={title}, snippet_date={snippet_date}, tags={tags} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.update_snippet(
                snippet_id=snippet_id,
                category=category,
                title=title,
                content=content,
                snippet_date=snippet_date,
                tags=tags,
            )
            logger.info(
                f"update_snippet response: success={response.success}, "
                f"status={response.status_code}"
            )

            snippet, snippet_error = validate_dict_response(response, "updated snippet")
            if snippet_error:
                logger.error(f"Failed to update snippet: {snippet_error}")
                return json.dumps({"error": snippet_error})

            logger.info(f"Updated snippet: id={snippet.get('id') if snippet else None}")
            return json.dumps(
                {
                    "snippet": snippet,
                    "status": "updated",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in update_snippet: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def delete_snippet(snippet_id: int) -> str:
        """
        Soft-delete a snippet.

        The snippet will no longer appear in listings or be fetchable, but its
        data is preserved internally.

        Args:
            snippet_id: Snippet ID to delete

        Returns:
            JSON object confirming deletion with deleted status and snippet id
        """
        logger.info(f"=== delete_snippet called: snippet_id={snippet_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.delete_snippet(snippet_id)
            logger.info(
                f"delete_snippet response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to delete snippet: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Deleted snippet {snippet_id}")
            return json.dumps(
                {
                    "snippet_id": snippet_id,
                    "status": "deleted",
                    "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in delete_snippet: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    # News / RSS feed tools

    @app.tool()
    @guard_tool(
        input_params=["unread_only", "search", "feed_type", "featured"],
        screen_output=True,
    )
    async def list_articles(
        unread_only: bool = False,
        search: str | None = None,
        feed_type: str | None = None,
        featured: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> str:
        """
        List news articles with optional filters.

        Browse curated articles from RSS/Atom feeds. Supports filtering by
        read status, keyword search, feed type, and featured sources.

        Args:
            unread_only: Only show unread articles (default False)
            search: Search in title and summary
            feed_type: Filter by "paper" or "article"
            featured: Filter by featured feed sources
            limit: Results per page (1-200, default 50)
            offset: Pagination offset (default 0)

        Returns:
            JSON object with "articles" array and pagination metadata
        """
        logger.info(
            f"=== list_articles called: unread_only={unread_only}, "
            f"search={search}, feed_type={feed_type}, featured={featured} ==="
        )
        valid_feed_types = {"paper", "article"}
        if feed_type is not None and feed_type not in valid_feed_types:
            return json.dumps(
                {
                    "error": (
                        f"Invalid feed_type '{feed_type}'. "
                        f"Must be one of: article, paper"
                    )
                }
            )
        try:
            api_client = get_api_client()
            response = api_client.list_articles(
                unread_only=unread_only,
                search=search,
                feed_type=feed_type,
                featured=featured,
                limit=limit,
                offset=offset,
            )
            logger.info(
                f"list_articles response: success={response.success}, "
                f"status={response.status_code}"
            )

            articles, articles_error = validate_list_response(
                response, "articles", key="data"
            )
            if articles_error:
                logger.error(f"Failed to list articles: {articles_error}")
                return json.dumps({"error": articles_error})

            # Extract pagination meta if present
            meta = {}
            if isinstance(response.data, dict):
                meta = response.data.get("meta", {})

            logger.info(f"Returning {len(articles)} articles")
            return json.dumps(
                {
                    "articles": articles,
                    "count": len(articles),
                    "meta": meta,
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in list_articles: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def get_article(article_id: int) -> str:
        """
        Get a single article by ID.

        Args:
            article_id: Article ID

        Returns:
            JSON object with full article data including title, url, summary,
            author, published_at, keywords, feed_source_name, is_read, rating
        """
        logger.info(f"=== get_article called: article_id={article_id} ===")
        try:
            api_client = get_api_client()
            response = api_client.get_article(article_id)
            logger.info(
                f"get_article response: success={response.success}, "
                f"status={response.status_code}"
            )

            article, article_error = validate_dict_response(response, "article")
            if article_error:
                logger.error(f"Failed to get article: {article_error}")
                return json.dumps({"error": article_error})

            logger.info(
                f"Retrieved article: id={article.get('id') if article else None}"
            )
            return json.dumps(
                {
                    "article": article,
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in get_article: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["is_read"], screen_output=True)
    async def mark_article_read(
        article_id: int, is_read: bool = True
    ) -> str:
        """
        Mark an article as read or unread.

        Args:
            article_id: Article ID
            is_read: True to mark read, False for unread (default True)

        Returns:
            JSON object confirming read status change
        """
        logger.info(
            f"=== mark_article_read called: article_id={article_id}, "
            f"is_read={is_read} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.mark_article_read(article_id, is_read)
            logger.info(
                f"mark_article_read response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to mark article read: {response.error}")
                return json.dumps({"error": response.error})

            result = response.data if isinstance(response.data, dict) else {}
            result["article_id"] = article_id
            result["status"] = "updated"
            result["current_time"] = datetime.datetime.now(
                tz=datetime.UTC
            ).isoformat()
            return json.dumps(result)
        except Exception as e:
            logger.error(
                f"Exception in mark_article_read: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["rating"], screen_output=True)
    async def rate_article(article_id: int, rating: str) -> str:
        """
        Rate an article.

        Args:
            article_id: Article ID
            rating: One of "good", "bad", "not_interested"

        Returns:
            JSON object confirming rating
        """
        logger.info(
            f"=== rate_article called: article_id={article_id}, "
            f"rating={rating} ==="
        )
        valid_ratings = {"good", "bad", "not_interested"}
        if rating not in valid_ratings:
            return json.dumps(
                {
                    "error": (
                        f"Invalid rating '{rating}'. "
                        f"Must be one of: {', '.join(sorted(valid_ratings))}"
                    )
                }
            )
        try:
            api_client = get_api_client()
            response = api_client.rate_article(article_id, rating)
            logger.info(
                f"rate_article response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to rate article: {response.error}")
                return json.dumps({"error": response.error})

            return json.dumps(
                {
                    "article_id": article_id,
                    "rating": rating,
                    "status": "rated",
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(f"Exception in rate_article: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["featured"], screen_output=True)
    async def list_feed_sources(featured: bool | None = None) -> str:
        """
        List RSS/Atom feed sources.

        Args:
            featured: Filter by featured status (optional)

        Returns:
            JSON object with "sources" array of feed sources
        """
        logger.info(
            f"=== list_feed_sources called: featured={featured} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.list_feed_sources(featured=featured)
            logger.info(
                f"list_feed_sources response: success={response.success}, "
                f"status={response.status_code}"
            )

            sources, sources_error = validate_list_response(
                response, "sources", key="data"
            )
            if sources_error:
                logger.error(f"Failed to list feed sources: {sources_error}")
                return json.dumps({"error": sources_error})

            logger.info(f"Returning {len(sources)} feed sources")
            return json.dumps(
                {
                    "sources": sources,
                    "count": len(sources),
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"Exception in list_feed_sources: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(
        input_params=["name", "url", "description", "feed_type"],
        screen_output=True,
    )
    async def create_feed_source(
        name: str,
        url: str,
        description: str | None = None,
        feed_type: str = "article",
        is_active: bool = True,
        is_featured: bool = False,
        fetch_interval_hours: int = 6,
    ) -> str:
        """
        Create a new RSS/Atom feed source (admin only).

        Args:
            name: Feed name (1-255 chars)
            url: Feed URL (1-500 chars)
            description: Feed description (optional)
            feed_type: "paper" or "article" (default "article")
            is_active: Whether feed is active (default True)
            is_featured: Whether feed is featured (default False)
            fetch_interval_hours: Fetch interval in hours, 1-168 (default 6)

        Returns:
            JSON object with created feed source data
        """
        logger.info(
            f"=== create_feed_source called: name='{name}', url='{url}', "
            f"feed_type={feed_type} ==="
        )
        valid_feed_types = {"paper", "article"}
        if feed_type not in valid_feed_types:
            return json.dumps(
                {
                    "error": (
                        f"Invalid feed_type '{feed_type}'. "
                        f"Must be one of: article, paper"
                    )
                }
            )
        try:
            api_client = get_api_client()
            response = api_client.create_feed_source(
                name=name,
                url=url,
                description=description,
                feed_type=feed_type,
                is_active=is_active,
                is_featured=is_featured,
                fetch_interval_hours=fetch_interval_hours,
            )
            logger.info(
                f"create_feed_source response: success={response.success}, "
                f"status={response.status_code}"
            )

            source, source_error = validate_dict_response(
                response, "feed source"
            )
            if source_error:
                logger.error(f"Failed to create feed source: {source_error}")
                return json.dumps({"error": source_error})

            logger.info(
                f"Created feed source: id={source.get('id') if source else None}"
            )
            return json.dumps(
                {
                    "source": source,
                    "status": "created",
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"Exception in create_feed_source: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(
        input_params=["name", "url", "description", "feed_type"],
        screen_output=True,
    )
    async def update_feed_source(
        source_id: int,
        name: str | None = None,
        url: str | None = None,
        description: str | None = None,
        feed_type: str | None = None,
        is_active: bool | None = None,
        is_featured: bool | None = None,
        fetch_interval_hours: int | None = None,
    ) -> str:
        """
        Update a feed source (admin only, partial update).

        Args:
            source_id: Feed source ID
            name: New name (optional)
            url: New URL (optional)
            description: New description (optional)
            feed_type: "paper" or "article" (optional)
            is_active: New active status (optional)
            is_featured: New featured status (optional)
            fetch_interval_hours: New fetch interval (optional)

        Returns:
            JSON object with updated feed source data
        """
        logger.info(
            f"=== update_feed_source called: source_id={source_id}, "
            f"name={name}, url={url} ==="
        )
        valid_feed_types = {"paper", "article"}
        if feed_type is not None and feed_type not in valid_feed_types:
            return json.dumps(
                {
                    "error": (
                        f"Invalid feed_type '{feed_type}'. "
                        f"Must be one of: article, paper"
                    )
                }
            )
        try:
            api_client = get_api_client()
            response = api_client.update_feed_source(
                source_id=source_id,
                name=name,
                url=url,
                description=description,
                feed_type=feed_type,
                is_active=is_active,
                is_featured=is_featured,
                fetch_interval_hours=fetch_interval_hours,
            )
            logger.info(
                f"update_feed_source response: success={response.success}, "
                f"status={response.status_code}"
            )

            source, source_error = validate_dict_response(
                response, "updated feed source"
            )
            if source_error:
                logger.error(f"Failed to update feed source: {source_error}")
                return json.dumps({"error": source_error})

            logger.info(
                f"Updated feed source: id={source.get('id') if source else None}"
            )
            return json.dumps(
                {
                    "source": source,
                    "status": "updated",
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"Exception in update_feed_source: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=[], screen_output=True)
    async def delete_feed_source(source_id: int) -> str:
        """
        Delete a feed source and its articles (admin only).

        This permanently removes the feed source and cascade-deletes all
        articles from that source.

        Args:
            source_id: Feed source ID to delete

        Returns:
            JSON object confirming deletion with deleted status
        """
        logger.info(
            f"=== delete_feed_source called: source_id={source_id} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.delete_feed_source(source_id)
            logger.info(
                f"delete_feed_source response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to delete feed source: {response.error}")
                return json.dumps({"error": response.error})

            logger.info(f"Deleted feed source {source_id}")
            return json.dumps(
                {
                    "source_id": source_id,
                    "status": "deleted",
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"Exception in delete_feed_source: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["is_active"], screen_output=True)
    async def toggle_feed_source(
        source_id: int, is_active: bool
    ) -> str:
        """
        Toggle a feed source's active status (admin only).

        Args:
            source_id: Feed source ID
            is_active: New active status

        Returns:
            JSON object confirming toggle
        """
        logger.info(
            f"=== toggle_feed_source called: source_id={source_id}, "
            f"is_active={is_active} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.toggle_feed_source(source_id, is_active)
            logger.info(
                f"toggle_feed_source response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(
                    f"Failed to toggle feed source: {response.error}"
                )
                return json.dumps({"error": response.error})

            result = response.data if isinstance(response.data, dict) else {}
            result["source_id"] = source_id
            result["status"] = "toggled"
            result["current_time"] = datetime.datetime.now(
                tz=datetime.UTC
            ).isoformat()
            return json.dumps(result)
        except Exception as e:
            logger.error(
                f"Exception in toggle_feed_source: {e}", exc_info=True
            )
            return json.dumps({"error": str(e)})

    @app.tool()
    @guard_tool(input_params=["hours"], screen_output=True)
    async def force_fetch_feed(
        source_id: int, hours: int = 168
    ) -> str:
        """
        Force-fetch articles from a feed source (admin only).

        Triggers an immediate fetch of articles from the specified feed source,
        looking back the specified number of hours.

        Args:
            source_id: Feed source ID
            hours: Hours back to fetch, 1-720 (default 168 = 1 week)

        Returns:
            JSON object with fetch result
        """
        logger.info(
            f"=== force_fetch_feed called: source_id={source_id}, "
            f"hours={hours} ==="
        )
        try:
            api_client = get_api_client()
            response = api_client.force_fetch_feed(source_id, hours)
            logger.info(
                f"force_fetch_feed response: success={response.success}, "
                f"status={response.status_code}"
            )

            if not response.success:
                logger.error(f"Failed to force fetch feed: {response.error}")
                return json.dumps({"error": response.error})

            result = response.data if isinstance(response.data, dict) else {}
            return json.dumps(
                {
                    "source_id": source_id,
                    "hours": hours,
                    "result": result,
                    "status": "fetched",
                    "current_time": datetime.datetime.now(
                        tz=datetime.UTC
                    ).isoformat(),
                }
            )
        except Exception as e:
            logger.error(
                f"Exception in force_fetch_feed: {e}", exc_info=True
            )
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
