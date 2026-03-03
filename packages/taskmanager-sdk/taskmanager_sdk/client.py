from typing import Any

import requests

from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import ApiResponse

VALID_DEADLINE_TYPES = ("flexible", "preferred", "firm", "hard")


class TaskManagerClient:
    """
    Python SDK client for TaskManager API.

    Provides methods for interacting with all TaskManager endpoints including
    authentication, project management, todo management, reporting, and OAuth.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000/api",
        session: requests.Session | None = None,
        access_token: str | None = None,
    ) -> None:
        """
        Initialize the TaskManager client.

        Args:
            base_url: Base URL for the TaskManager API
            session: Optional requests session to use for HTTP calls
            access_token: Optional OAuth access token for Bearer auth
        """
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )
        self.cookies: dict[str, str] = {}
        self.access_token: str | None = access_token
        self.token_expires_at: float | None = None

    def _build_params(self, **kwargs: Any) -> dict[str, Any]:
        """Build a params/data dict, omitting keys whose value is None.

        Args:
            **kwargs: Key-value pairs to include when not None

        Returns:
            dict with only non-None values
        """
        return {k: v for k, v in kwargs.items() if v is not None}

    def _validate_deadline_type(self, deadline_type: str | None) -> None:
        """Validate deadline_type value.

        Args:
            deadline_type: Deadline type string to validate, or None (no-op)

        Raises:
            ValidationError: If deadline_type is not one of the valid values
        """
        if deadline_type is not None and deadline_type not in VALID_DEADLINE_TYPES:
            raise ValidationError(
                f"Invalid deadline_type: {deadline_type!r}. "
                f"Must be one of: {', '.join(VALID_DEADLINE_TYPES)}"
            )

    def _make_form_request(
        self,
        endpoint: str,
        form_data: dict[str, str],
        error_key: str = "error",
        fallback_error_key: str | None = None,
        raise_on_401: bool = True,
        raise_on_5xx: bool = True,
    ) -> ApiResponse:
        """Make a form-encoded POST request (used by OAuth endpoints).

        Args:
            endpoint: API endpoint path
            form_data: Form fields to send as application/x-www-form-urlencoded
            error_key: JSON key to read error message from (default "error")
            fallback_error_key: Secondary JSON key to try if error_key not found
            raise_on_401: Whether to raise AuthenticationError on 401
            raise_on_5xx: Whether to raise ServerError on 5xx

        Returns:
            ApiResponse object

        Raises:
            NetworkError: For connection/network issues
            AuthenticationError: For 401 status codes (when raise_on_401 is True)
            ServerError: For 5xx status codes (when raise_on_5xx is True)
        """
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Add Bearer token if available
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = self.session.post(
                url,
                data=form_data,
                headers=headers,
                cookies=self.cookies,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    if fallback_error_key is not None:
                        error_message = error_data.get(
                            error_key,
                            error_data.get(
                                fallback_error_key, f"HTTP {response.status_code}"
                            ),
                        )
                    else:
                        error_message = error_data.get(
                            error_key, f"HTTP {response.status_code}"
                        )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                if raise_on_401 and response.status_code == 401:
                    raise AuthenticationError(error_message)
                if raise_on_5xx and response.status_code >= 500:
                    raise ServerError(error_message)

                return ApiResponse(
                    success=False, error=error_message, status_code=response.status_code
                )

            try:
                json_data = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                json_data = None

            return ApiResponse(
                success=True, data=json_data, status_code=response.status_code
            )

        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e)) from e

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiResponse:
        """
        Make HTTP request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: JSON data for request body
            params: Query parameters

        Returns:
            ApiResponse object with success status, data, and error information

        Raises:
            NetworkError: For connection/network issues
            AuthenticationError: For 401 status codes
            AuthorizationError: For 403 status codes
            NotFoundError: For 404 status codes
            ValidationError: For 400 status codes
            RateLimitError: For 429 status codes
            ServerError: For 5xx status codes
        """
        url = f"{self.base_url}{endpoint}"

        # Build headers with Bearer token auth if available
        headers: dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            method_name = method.upper()
            request_func = getattr(self.session, method_name.lower(), None)
            if request_func is None:
                return ApiResponse(
                    success=False, error=f"Unsupported HTTP method: {method}"
                )

            kwargs: dict[str, Any] = {
                "params": params,
                "cookies": self.cookies,
                "headers": headers,
            }
            if method_name in ("POST", "PUT", "PATCH"):
                kwargs["json"] = data

            response = request_func(url, **kwargs)

            # Handle cookie authentication
            if "set-cookie" in response.headers:
                split_cookie = response.headers["set-cookie"].split("=", 1)
                if len(split_cookie) == 2:
                    self.cookies[split_cookie[0]] = split_cookie[1].split(";")[0]

            # Handle error status codes with appropriate exceptions
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    # FastAPI format: {"detail": {"code": "...", "message": "..."}}
                    # Legacy format: {"error": "..."}
                    if "detail" in error_data and isinstance(
                        error_data["detail"], dict
                    ):
                        error_message = error_data["detail"].get(
                            "message", f"HTTP {response.status_code}"
                        )
                    else:
                        error_message = error_data.get(
                            "error", f"HTTP {response.status_code}"
                        )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                api_response = ApiResponse(
                    success=False, error=error_message, status_code=response.status_code
                )

                # Raise appropriate exception based on status code
                if response.status_code == 401:
                    raise AuthenticationError(error_message)
                elif response.status_code == 403:
                    raise AuthorizationError(error_message)
                elif response.status_code == 404:
                    raise NotFoundError(error_message)
                elif response.status_code == 400:
                    raise ValidationError(error_message)
                elif response.status_code == 429:
                    raise RateLimitError(error_message)
                elif response.status_code >= 500:
                    raise ServerError(error_message)

                return api_response

            # Parse JSON response
            try:
                json_data = response.json()
                # FastAPI wraps responses in {"data": ..., "meta": {...}}
                # Extract the data field if present, otherwise return as-is
                if isinstance(json_data, dict) and "data" in json_data:
                    json_data = json_data["data"]
            except (ValueError, requests.exceptions.JSONDecodeError):
                json_data = None

            return ApiResponse(
                success=True, data=json_data, status_code=response.status_code
            )

        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e)) from e

    # Health check
    def health_check(self) -> ApiResponse:
        """Check backend health with per-subsystem status.

        Calls GET /health on the backend root (outside /api).

        Returns:
            ApiResponse with status, subsystems, and timestamp
        """
        # Strip /api suffix to reach the root health endpoint
        root_url = self.base_url
        if root_url.endswith("/api"):
            root_url = root_url[:-4]

        url = f"{root_url}/health"
        headers: dict[str, str] = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = self.session.get(url, headers=headers, cookies=self.cookies)
            try:
                json_data = response.json()
            except (ValueError, requests.exceptions.JSONDecodeError):
                json_data = None
            return ApiResponse(
                success=response.status_code == 200,
                data=json_data,
                status_code=response.status_code,
            )
        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e)) from e

    # Authentication methods
    def login(self, email: str, password: str) -> ApiResponse:
        """
        Authenticate user with email and password.

        Args:
            email: User's email address
            password: User's password

        Returns:
            ApiResponse with authentication result
        """
        return self._make_request(
            "POST", "/auth/login", {"email": email, "password": password}
        )

    def register(self, email: str, password: str) -> ApiResponse:
        """
        Register a new user account.

        Args:
            email: User's email address
            password: User's password

        Returns:
            ApiResponse with registration result
        """
        return self._make_request(
            "POST",
            "/auth/register",
            {"email": email, "password": password},
        )

    def logout(self) -> ApiResponse:
        """
        Log out the current user session.

        Returns:
            ApiResponse with logout result
        """
        return self._make_request("POST", "/auth/logout")

    # Project methods
    def get_projects(self) -> ApiResponse:
        """
        Get all projects for the authenticated user.

        Returns:
            ApiResponse with list of projects
        """
        return self._make_request("GET", "/projects")

    def create_project(
        self,
        name: str,
        description: str | None = None,
        color: str | None = None,
        show_on_calendar: bool | None = None,
    ) -> ApiResponse:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description
            color: Optional project color (hex format: #RRGGBB)
            show_on_calendar: Whether to show this project's tasks on
                calendar and home dashboard (default: true)

        Returns:
            ApiResponse with created project data
        """
        return self._make_request(
            "POST",
            "/projects",
            {
                "name": name,
                **self._build_params(
                    description=description,
                    color=color,
                    show_on_calendar=show_on_calendar,
                ),
            },
        )

    def get_project(self, project_id: int) -> ApiResponse:
        """
        Get a specific project by ID.

        Args:
            project_id: Project ID

        Returns:
            ApiResponse with project data
        """
        return self._make_request("GET", f"/projects/{project_id}")

    def update_project(
        self,
        project_id: int,
        name: str | None = None,
        color: str | None = None,
        description: str | None = None,
    ) -> ApiResponse:
        """
        Update a project.

        Args:
            project_id: Project ID to update
            name: New project name
            color: New project color
            description: New project description

        Returns:
            ApiResponse with updated project data
        """
        return self._make_request(
            "PUT",
            f"/projects/{project_id}",
            self._build_params(name=name, color=color, description=description),
        )

    def delete_project(self, project_id: int) -> ApiResponse:
        """
        Delete a project.

        Args:
            project_id: Project ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/projects/{project_id}")

    # Todo methods
    def get_todos(
        self,
        project_id: int | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        category: str | None = None,
        deadline_type: str | None = None,
        limit: int | None = None,
        include_subtasks: bool = False,
        order_by: str | None = None,
    ) -> ApiResponse:
        """
        Get todos with optional filtering.

        Args:
            project_id: Filter by project ID
            status: Filter by status
                (pending, in_progress, completed, cancelled, overdue, all)
            start_date: Filter tasks with due_date on or after this date (ISO format)
            end_date: Filter tasks with due_date on or before this date (ISO format)
            category: Filter by category name (project name)
            deadline_type: Filter by deadline type (flexible, preferred, firm, hard)
            limit: Maximum number of tasks to return
            include_subtasks: Include subtasks in the response (default: False)
            order_by: Sort order (position, due_date, or deadline_type)

        Returns:
            ApiResponse with TaskListResponse data
        """
        self._validate_deadline_type(deadline_type)
        if order_by is not None:
            valid_order_by = ("position", "due_date", "deadline_type")
            if order_by not in valid_order_by:
                raise ValidationError(
                    f"Invalid order_by: {order_by!r}. "
                    f"Must be one of: {', '.join(valid_order_by)}"
                )
        params = self._build_params(
            project_id=project_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            category=category,
            deadline_type=deadline_type,
            limit=limit,
            order_by=order_by,
        )
        if include_subtasks:
            params["include_subtasks"] = True
        return self._make_request("GET", "/todos", params=params)

    def create_todo(
        self,
        title: str,
        project_id: int | None = None,
        description: str | None = None,
        category: str | None = None,
        priority: str = "medium",
        estimated_hours: float | None = None,
        due_date: str | None = None,
        deadline_type: str | None = None,
        tags: list[str] | None = None,
        parent_id: int | None = None,
    ) -> ApiResponse:
        """
        Create a new todo item or subtask.

        Args:
            title: Todo title
            project_id: Optional project ID (alternative to category)
            description: Optional description
            category: Task category name (maps to project)
            priority: Priority level (low, medium, high, urgent)
            estimated_hours: Estimated hours to complete
            due_date: Due date in ISO format
            deadline_type: How strict the due date is (flexible, preferred, firm, hard)
            tags: list of tags
            parent_id: Parent todo ID to create a subtask (optional)

        Returns:
            ApiResponse with TaskCreateResponse data
        """
        self._validate_deadline_type(deadline_type)
        return self._make_request(
            "POST",
            "/todos",
            {
                "title": title,
                **self._build_params(
                    project_id=project_id,
                    description=description,
                    category=category,
                    priority=priority,
                    estimated_hours=estimated_hours,
                    due_date=due_date,
                    deadline_type=deadline_type,
                    tags=tags,
                    parent_id=parent_id,
                ),
            },
        )

    def batch_create_todos(
        self,
        todos: list[dict[str, Any]],
        skip_duplicates: bool = False,
        wiki_page_id: int | None = None,
    ) -> ApiResponse:
        """
        Create multiple todos in a single request.

        Args:
            todos: List of todo dicts, each with at least a "title" key.
                   Supports the same fields as create_todo (description,
                   category, priority, due_date, deadline_type, tags,
                   parent_id, etc.) plus:
                   - depends_on: List of 0-based indices of other tasks in
                     the batch that this task depends on.
            skip_duplicates: If true, silently skip todos whose title
                             matches an existing active todo instead of
                             rejecting the batch.
            wiki_page_id: Optional wiki page ID to auto-link to all
                          created tasks.

        Returns:
            ApiResponse with list of created todos
        """
        data: dict[str, Any] = {
            "todos": todos,
            **self._build_params(wiki_page_id=wiki_page_id),
        }
        if skip_duplicates:
            data["skip_duplicates"] = True
        return self._make_request("POST", "/todos/batch", data)

    def get_todo(self, todo_id: int) -> ApiResponse:
        """
        Get a specific todo by ID.

        Args:
            todo_id: Todo ID

        Returns:
            ApiResponse with todo data
        """
        return self._make_request("GET", f"/todos/{todo_id}")

    def update_todo(
        self,
        todo_id: int,
        title: str | None = None,
        description: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        estimated_hours: float | None = None,
        actual_hours: float | None = None,
        status: str | None = None,
        due_date: str | None = None,
        deadline_type: str | None = None,
        tags: list[str] | None = None,
        parent_id: int | None = None,
        agent_actionable: bool | None = None,
        action_type: str | None = None,
        autonomy_tier: int | None = None,
        agent_status: str | None = None,
        agent_notes: str | None = None,
        blocking_reason: str | None = None,
    ) -> ApiResponse:
        """
        Update a todo item.

        Args:
            todo_id: Todo ID to update
            title: New title
            description: New description
            category: New category name (maps to project)
            priority: New priority (low, medium, high, urgent)
            estimated_hours: New estimated hours
            actual_hours: Actual hours spent
            status: New status (pending, in_progress, completed, cancelled)
            due_date: New due date (for rescheduling)
            deadline_type: How strict the due date is (flexible, preferred, firm, hard)
            tags: New tags list
            parent_id: New parent ID to move task (optional)
            agent_actionable: Whether an AI agent can complete this task autonomously
            action_type: Type of action (research, code, email, etc.)
            autonomy_tier: Risk level 1-4 (1=fully autonomous, 4=never autonomous)
            agent_status: Agent processing status (pending_review, in_progress, etc.)
            agent_notes: Agent-generated notes and context
            blocking_reason: Why agent cannot proceed (if blocked)

        Returns:
            ApiResponse with TaskUpdateResponse data
        """
        self._validate_deadline_type(deadline_type)
        return self._make_request(
            "PUT",
            f"/todos/{todo_id}",
            self._build_params(
                title=title,
                description=description,
                category=category,
                priority=priority,
                estimated_hours=estimated_hours,
                actual_hours=actual_hours,
                status=status,
                due_date=due_date,
                deadline_type=deadline_type,
                tags=tags,
                parent_id=parent_id,
                agent_actionable=agent_actionable,
                action_type=action_type,
                autonomy_tier=autonomy_tier,
                agent_status=agent_status,
                agent_notes=agent_notes,
                blocking_reason=blocking_reason,
            ),
        )

    def delete_todo(self, todo_id: int) -> ApiResponse:
        """
        Delete a todo item.

        Args:
            todo_id: Todo ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/todos/{todo_id}")

    def complete_todo(
        self, todo_id: int, actual_hours: float | None = None
    ) -> ApiResponse:
        """
        Mark a todo as completed.

        Args:
            todo_id: Todo ID to complete
            actual_hours: Optional actual hours spent on the todo

        Returns:
            ApiResponse with completion result
        """
        return self._make_request(
            "POST",
            f"/todos/{todo_id}/complete",
            self._build_params(actual_hours=actual_hours),
        )

    def get_attachments(self, todo_id: int) -> ApiResponse:
        """
        Get all attachments for a todo.

        Args:
            todo_id: Todo ID

        Returns:
            ApiResponse with list of attachments
        """
        return self._make_request("GET", f"/todos/{todo_id}/attachments")

    # Comment methods
    def get_comments(self, todo_id: int) -> ApiResponse:
        """
        Get all comments for a todo.

        Args:
            todo_id: Todo ID

        Returns:
            ApiResponse with list of comments
        """
        return self._make_request("GET", f"/todos/{todo_id}/comments")

    def create_comment(self, todo_id: int, content: str) -> ApiResponse:
        """
        Create a comment on a todo.

        Args:
            todo_id: Todo ID
            content: Comment text content

        Returns:
            ApiResponse with created comment data
        """
        return self._make_request(
            "POST", f"/todos/{todo_id}/comments", {"content": content}
        )

    def update_comment(
        self, todo_id: int, comment_id: int, content: str
    ) -> ApiResponse:
        """
        Update a comment's content.

        Args:
            todo_id: Todo ID
            comment_id: Comment ID to update
            content: New comment text content

        Returns:
            ApiResponse with updated comment data
        """
        return self._make_request(
            "PUT", f"/todos/{todo_id}/comments/{comment_id}", {"content": content}
        )

    def delete_comment(self, todo_id: int, comment_id: int) -> ApiResponse:
        """
        Delete a comment from a todo (soft-delete).

        Args:
            todo_id: Todo ID
            comment_id: Comment ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/todos/{todo_id}/comments/{comment_id}")

    def delete_attachment(self, todo_id: int, attachment_id: int) -> ApiResponse:
        """
        Delete an attachment from a todo.

        Args:
            todo_id: Todo ID
            attachment_id: Attachment ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request(
            "DELETE", f"/todos/{todo_id}/attachments/{attachment_id}"
        )

    # Wiki methods
    def list_wiki_pages(self, q: str | None = None) -> ApiResponse:
        """
        List wiki pages for the current user.

        Args:
            q: Optional search query to filter pages by title or content

        Returns:
            ApiResponse with list of wiki page summaries
        """
        params = self._build_params(q=q)
        return self._make_request("GET", "/wiki", params=params or None)

    def create_wiki_page(
        self,
        title: str,
        content: str = "",
        slug: str | None = None,
        parent_id: int | None = None,
    ) -> ApiResponse:
        """
        Create a new wiki page.

        Args:
            title: Page title (required, 1-500 chars)
            content: Page content in markdown (default: "")
            slug: Optional URL slug (auto-generated from title if not provided)
            parent_id: Optional parent page ID for nesting under another page

        Returns:
            ApiResponse with created wiki page data
        """
        return self._make_request(
            "POST",
            "/wiki",
            {
                "title": title,
                "content": content,
                **self._build_params(slug=slug, parent_id=parent_id),
            },
        )

    def get_wiki_page(self, slug_or_id: str | int) -> ApiResponse:
        """
        Get a wiki page by slug or numeric ID.

        Args:
            slug_or_id: Page slug string or numeric ID

        Returns:
            ApiResponse with wiki page data including content
        """
        return self._make_request("GET", f"/wiki/{slug_or_id}")

    def update_wiki_page(
        self,
        page_id: int,
        title: str | None = None,
        content: str | None = None,
        slug: str | None = None,
        append: bool = False,
        parent_id: int | None = None,
        remove_parent: bool = False,
    ) -> ApiResponse:
        """
        Update a wiki page.

        Args:
            page_id: Wiki page ID
            title: New title (optional)
            content: New content (optional)
            slug: New slug (optional)
            append: If True, append content instead of replacing (default False)
            parent_id: New parent page ID to move page under (optional)
            remove_parent: If True, remove the parent (make page a root page)

        Returns:
            ApiResponse with updated wiki page data
        """
        if parent_id is not None and remove_parent:
            raise ValueError("parent_id and remove_parent are mutually exclusive")
        data = self._build_params(
            title=title, content=content, slug=slug, parent_id=parent_id
        )
        if append:
            data["append"] = True
        if remove_parent:
            data["remove_parent"] = True
        return self._make_request("PUT", f"/wiki/{page_id}", data)

    def delete_wiki_page(self, page_id: int) -> ApiResponse:
        """
        Delete a wiki page.

        Args:
            page_id: Wiki page ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/wiki/{page_id}")

    def link_wiki_page_to_task(self, page_id: int, todo_id: int) -> ApiResponse:
        """
        Link a wiki page to a task.

        Args:
            page_id: Wiki page ID
            todo_id: Task ID to link

        Returns:
            ApiResponse with linked task data
        """
        return self._make_request(
            "POST", f"/wiki/{page_id}/link-task", {"todo_id": todo_id}
        )

    def unlink_wiki_page_from_task(self, page_id: int, todo_id: int) -> ApiResponse:
        """
        Unlink a wiki page from a task.

        Args:
            page_id: Wiki page ID
            todo_id: Task ID to unlink

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/wiki/{page_id}/link-task/{todo_id}")

    def get_wiki_page_linked_tasks(self, page_id: int) -> ApiResponse:
        """
        Get tasks linked to a wiki page.

        Args:
            page_id: Wiki page ID

        Returns:
            ApiResponse with list of linked tasks
        """
        return self._make_request("GET", f"/wiki/{page_id}/linked-tasks")

    def get_task_wiki_pages(self, todo_id: int) -> ApiResponse:
        """
        Get wiki pages linked to a task.

        Args:
            todo_id: Task ID

        Returns:
            ApiResponse with list of wiki page summaries
        """
        return self._make_request("GET", f"/todos/{todo_id}/wiki-pages")

    def batch_link_wiki_page_to_tasks(
        self, page_id: int, todo_ids: list[int]
    ) -> ApiResponse:
        """
        Batch link a wiki page to multiple tasks at once.

        Args:
            page_id: Wiki page ID
            todo_ids: List of task IDs to link

        Returns:
            ApiResponse with linked, already_linked, and not_found lists
        """
        return self._make_request(
            "POST", f"/wiki/{page_id}/link-tasks", {"todo_ids": todo_ids}
        )

    def get_wiki_page_revisions(self, page_id: int) -> ApiResponse:
        """
        List revisions for a wiki page.

        Args:
            page_id: Wiki page ID

        Returns:
            ApiResponse with list of revision summaries
        """
        return self._make_request("GET", f"/wiki/{page_id}/revisions")

    def get_wiki_page_revision(self, page_id: int, revision_number: int) -> ApiResponse:
        """
        Get a specific revision of a wiki page.

        Args:
            page_id: Wiki page ID
            revision_number: Revision number to fetch

        Returns:
            ApiResponse with revision data including content
        """
        return self._make_request("GET", f"/wiki/{page_id}/revisions/{revision_number}")

    # Snippet methods
    def list_snippets(
        self,
        q: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> ApiResponse:
        """
        List snippets with optional filters.

        Args:
            q: Search query (searches title, content, category)
            category: Filter by category
            tag: Filter by tag
            date_from: Filter snippets from this date (YYYY-MM-DD)
            date_to: Filter snippets up to this date (YYYY-MM-DD)

        Returns:
            ApiResponse with list of snippet summaries
        """
        params = self._build_params(
            q=q, category=category, tag=tag, date_from=date_from, date_to=date_to
        )
        return self._make_request("GET", "/snippets", params=params or None)

    def create_snippet(
        self,
        category: str,
        title: str,
        content: str = "",
        snippet_date: str | None = None,
        tags: list[str] | None = None,
    ) -> ApiResponse:
        """
        Create a new snippet.

        Args:
            category: Snippet category (required)
            title: Snippet title (required)
            content: Snippet content (optional, default "")
            snippet_date: Date for the snippet, YYYY-MM-DD
                          (optional, defaults to today)
            tags: List of tags (optional)

        Returns:
            ApiResponse with created snippet data
        """
        return self._make_request(
            "POST",
            "/snippets",
            {
                "category": category,
                "title": title,
                "content": content,
                **self._build_params(snippet_date=snippet_date, tags=tags),
            },
        )

    def get_snippet(self, snippet_id: int) -> ApiResponse:
        """
        Get a snippet by ID.

        Args:
            snippet_id: Snippet ID

        Returns:
            ApiResponse with full snippet data
        """
        return self._make_request("GET", f"/snippets/{snippet_id}")

    def update_snippet(
        self,
        snippet_id: int,
        category: str | None = None,
        title: str | None = None,
        content: str | None = None,
        snippet_date: str | None = None,
        tags: list[str] | None = None,
    ) -> ApiResponse:
        """
        Update an existing snippet.

        Args:
            snippet_id: Snippet ID
            category: New category (optional)
            title: New title (optional)
            content: New content (optional)
            snippet_date: New date in YYYY-MM-DD format (optional)
            tags: New tags (optional)

        Returns:
            ApiResponse with updated snippet data
        """
        return self._make_request(
            "PUT",
            f"/snippets/{snippet_id}",
            self._build_params(
                category=category,
                title=title,
                content=content,
                snippet_date=snippet_date,
                tags=tags,
            ),
        )

    def delete_snippet(self, snippet_id: int) -> ApiResponse:
        """
        Delete a snippet (soft-delete).

        Args:
            snippet_id: Snippet ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/snippets/{snippet_id}")

    def get_snippet_categories(self) -> ApiResponse:
        """
        Get snippet categories with counts.

        Returns:
            ApiResponse with list of categories and their snippet counts
        """
        return self._make_request("GET", "/snippets/categories")

    # News / RSS feed methods
    def list_articles(
        self,
        unread_only: bool = False,
        search: str | None = None,
        feed_type: str | None = None,
        featured: bool | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> ApiResponse:
        """
        List news articles with optional filters.

        Args:
            unread_only: Only show unread articles (default False)
            search: Search in title and summary
            feed_type: Filter by "paper" or "article"
            featured: Filter by featured feed sources
            limit: Results per page (1-200, default 50)
            offset: Pagination offset (default 0)

        Returns:
            ApiResponse with list of articles and pagination meta
        """
        params = self._build_params(
            search=search,
            feed_type=feed_type,
            featured=featured,
            limit=limit,
            offset=offset,
        )
        if unread_only:
            params["unread_only"] = True
        return self._make_request("GET", "/news", params=params or None)

    def get_article(self, article_id: int) -> ApiResponse:
        """
        Get a single article by ID.

        Args:
            article_id: Article ID

        Returns:
            ApiResponse with article data
        """
        return self._make_request("GET", f"/news/{article_id}")

    def mark_article_read(self, article_id: int, is_read: bool = True) -> ApiResponse:
        """
        Mark an article as read or unread.

        Args:
            article_id: Article ID
            is_read: True to mark read, False for unread (default True)

        Returns:
            ApiResponse with read status
        """
        return self._make_request(
            "POST", f"/news/{article_id}/read", {"is_read": is_read}
        )

    def rate_article(self, article_id: int, rating: str) -> ApiResponse:
        """
        Rate an article.

        Args:
            article_id: Article ID
            rating: One of "good", "bad", "not_interested"

        Returns:
            ApiResponse with rating data
        """
        return self._make_request(
            "POST", f"/news/{article_id}/rate", {"rating": rating}
        )

    def list_feed_sources(self, featured: bool | None = None) -> ApiResponse:
        """
        List RSS/Atom feed sources.

        Args:
            featured: Filter by featured status (optional)

        Returns:
            ApiResponse with list of feed sources
        """
        params = self._build_params(featured=featured)
        return self._make_request("GET", "/news/sources", params=params or None)

    def create_feed_source(
        self,
        name: str,
        url: str,
        description: str | None = None,
        feed_type: str = "article",
        is_active: bool = True,
        is_featured: bool = False,
        fetch_interval_hours: int = 6,
    ) -> ApiResponse:
        """
        Create a new RSS/Atom feed source (admin only).

        Args:
            name: Feed name (1-255 chars)
            url: Feed URL (1-500 chars)
            description: Feed description (optional)
            feed_type: "paper" or "article" (default "article")
            is_active: Whether feed is active (default True)
            is_featured: Whether feed is featured (default False)
            fetch_interval_hours: Fetch interval, 1-168 (default 6)

        Returns:
            ApiResponse with created feed source data
        """
        return self._make_request(
            "POST",
            "/news/sources",
            {
                "name": name,
                "url": url,
                "type": feed_type,
                "is_active": is_active,
                "is_featured": is_featured,
                "fetch_interval_hours": fetch_interval_hours,
                **self._build_params(description=description),
            },
        )

    def update_feed_source(
        self,
        source_id: int,
        name: str | None = None,
        url: str | None = None,
        description: str | None = None,
        feed_type: str | None = None,
        is_active: bool | None = None,
        is_featured: bool | None = None,
        fetch_interval_hours: int | None = None,
    ) -> ApiResponse:
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
            ApiResponse with updated feed source data
        """
        data = self._build_params(
            name=name,
            url=url,
            description=description,
            is_active=is_active,
            is_featured=is_featured,
            fetch_interval_hours=fetch_interval_hours,
        )
        if feed_type is not None:
            data["type"] = feed_type
        return self._make_request("PUT", f"/news/sources/{source_id}", data)

    def delete_feed_source(self, source_id: int) -> ApiResponse:
        """
        Delete a feed source and its articles (admin only).

        Args:
            source_id: Feed source ID

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/news/sources/{source_id}")

    def toggle_feed_source(self, source_id: int, is_active: bool) -> ApiResponse:
        """
        Toggle a feed source's active status (admin only).

        Args:
            source_id: Feed source ID
            is_active: New active status

        Returns:
            ApiResponse with toggle result
        """
        return self._make_request(
            "POST",
            f"/news/sources/{source_id}/toggle",
            {"is_active": is_active},
        )

    def force_fetch_feed(self, source_id: int, hours: int = 168) -> ApiResponse:
        """
        Force-fetch articles from a feed source (admin only).

        Args:
            source_id: Feed source ID
            hours: Hours back to fetch, 1-720 (default 168)

        Returns:
            ApiResponse with fetch result
        """
        return self._make_request(
            "POST",
            f"/news/sources/{source_id}/fetch",
            {"hours": hours},
        )

    # Dependency methods
    def get_dependencies(self, todo_id: int) -> ApiResponse:
        """
        Get all dependencies for a todo (tasks it depends on).

        Args:
            todo_id: Todo ID

        Returns:
            ApiResponse with list of dependency tasks
        """
        return self._make_request("GET", f"/todos/{todo_id}/dependencies")

    def add_dependency(self, todo_id: int, dependency_id: int) -> ApiResponse:
        """
        Add a dependency to a todo.

        The dependency_id specifies the task that must be completed before this task.

        Args:
            todo_id: Todo ID (the dependent task)
            dependency_id: ID of the task this task depends on

        Returns:
            ApiResponse with created dependency data
        """
        return self._make_request(
            "POST", f"/todos/{todo_id}/dependencies", {"dependency_id": dependency_id}
        )

    def remove_dependency(self, todo_id: int, dependency_id: int) -> ApiResponse:
        """
        Remove a dependency from a todo.

        Args:
            todo_id: Todo ID (the dependent task)
            dependency_id: ID of the dependency task to remove

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request(
            "DELETE", f"/todos/{todo_id}/dependencies/{dependency_id}"
        )

    # Category methods
    def get_categories(self) -> ApiResponse:
        """
        Get all task categories with task counts.

        Returns:
            ApiResponse with CategoryListResponse data
        """
        return self._make_request("GET", "/categories")

    # Search methods
    def search_tasks(self, query: str, category: str | None = None) -> ApiResponse:
        """
        Search tasks by keyword using full-text search.

        Args:
            query: Search query string
            category: Optional filter results by category name

        Returns:
            ApiResponse with TaskSearchResponse data
        """
        return self._make_request(
            "GET",
            "/tasks/search",
            params={"q": query, **self._build_params(category=category)},
        )

    # OAuth methods
    def get_oauth_clients(self) -> ApiResponse:
        """
        Get OAuth clients for the authenticated user.

        Returns:
            ApiResponse with list of OAuth clients
        """
        return self._make_request("GET", "/oauth/clients")

    def get_oauth_client_info(self, client_id: str) -> ApiResponse:
        """
        Get OAuth client information by client ID.

        This endpoint requires client credentials authentication and can fetch
        any client's metadata (not restricted to the authenticated user's clients).
        Designed for machine-to-machine services like MCP auth servers.

        Args:
            client_id: The OAuth client ID to look up

        Returns:
            ApiResponse with client information
        """
        return self._make_request("GET", f"/oauth/clients/{client_id}/info")

    def create_oauth_client(
        self,
        name: str,
        redirect_uris: list[str],
        grant_types: list[str] | None = None,
        scopes: list[str] | None = None,
        token_endpoint_auth_method: str | None = None,
    ) -> ApiResponse:
        """
        Create a new OAuth client.

        Args:
            name: Client name
            redirect_uris: list of redirect URIs
            grant_types: list of grant types
            scopes: list of scopes
            token_endpoint_auth_method: Authentication method for token endpoint.
                Use "none" for public clients (native apps, SPAs, device flow).
                Use "client_secret_post" for confidential clients (default).

        Returns:
            ApiResponse with created OAuth client data
        """
        return self._make_request(
            "POST",
            "/oauth/clients",
            {
                "name": name,
                "redirectUris": redirect_uris,
                **self._build_params(
                    grantTypes=grant_types,
                    scopes=scopes,
                    token_endpoint_auth_method=token_endpoint_auth_method,
                ),
            },
        )

    def create_system_oauth_client(
        self,
        name: str,
        redirect_uris: list[str],
        grant_types: list[str] | None = None,
        scopes: list[str] | None = None,
        token_endpoint_auth_method: str | None = None,
    ) -> ApiResponse:
        """
        Create a system OAuth client (for dynamic client registration).

        This endpoint requires client credentials authentication and creates
        OAuth clients that are not owned by a specific user. Designed for
        machine-to-machine services like MCP auth servers.

        Args:
            name: Client name
            redirect_uris: list of redirect URIs
            grant_types: list of grant types
            scopes: list of scopes
            token_endpoint_auth_method: Authentication method for token endpoint.
                Use "none" for public clients (native apps, SPAs, device flow).
                Use "client_secret_post" for confidential clients (default).

        Returns:
            ApiResponse with created OAuth client data
        """
        return self._make_request(
            "POST",
            "/oauth/clients/system",
            {
                "name": name,
                "redirectUris": redirect_uris,
                **self._build_params(
                    grantTypes=grant_types,
                    scopes=scopes,
                    token_endpoint_auth_method=token_endpoint_auth_method,
                ),
            },
        )

    def update_oauth_client(
        self,
        client_id: str,
        name: str,
        redirect_uris: list[str],
        grant_types: list[str] | None = None,
        scopes: list[str] | None = None,
    ) -> ApiResponse:
        """
        Update an OAuth client.

        Args:
            client_id: OAuth client ID to update
            name: Client name
            redirect_uris: List of redirect URIs
            grant_types: List of grant types (defaults to ['authorization_code'])
            scopes: List of scopes (defaults to ['read'])

        Returns:
            ApiResponse with updated OAuth client data
        """
        return self._make_request(
            "PUT",
            f"/oauth/clients/{client_id}",
            {
                "name": name,
                "redirectUris": redirect_uris,
                **self._build_params(grantTypes=grant_types, scopes=scopes),
            },
        )

    def delete_oauth_client(self, client_id: str) -> ApiResponse:
        """
        Delete an OAuth client.

        Args:
            client_id: OAuth client ID to delete

        Returns:
            ApiResponse with deletion result
        """
        return self._make_request("DELETE", f"/oauth/clients/{client_id}")

    def get_jwks(self) -> ApiResponse:
        """
        Get JSON Web Key Set.

        Returns:
            ApiResponse with JWKS data
        """
        return self._make_request("GET", "/oauth/jwks")

    def verify_token(self) -> ApiResponse:
        """
        Verify OAuth access token.

        Works for both user tokens and client credentials tokens.
        Returns token information including validity, scopes, and expiration.

        Returns:
            ApiResponse with token verification data:
            {
                "valid": bool,
                "client_id": str,
                "user_id": int | None,
                "scopes": list[str],
                "expires_in": int,
                "token_type": str
            }
        """
        return self._make_request("GET", "/oauth/verify")

    def request_device_code(
        self, client_id: str, scope: str | None = None
    ) -> ApiResponse:
        """
        Request device authorization code (RFC 8628).

        Initiates the OAuth 2.0 Device Authorization Grant flow.
        The CLI calls this endpoint to get a device code and user code.
        The user then visits the verification URL and enters the user code.

        Args:
            client_id: OAuth client ID
            scope: Space-separated list of requested scopes (optional)

        Returns:
            ApiResponse with DeviceAuthorizationResponse data
        """
        form_data: dict[str, str] = {
            "client_id": client_id,
            **self._build_params(scope=scope),
        }
        return self._make_form_request(
            "/oauth/device/code",
            form_data,
            error_key="error_description",
            fallback_error_key="error",
        )

    def authorize_device(self, user_code: str, action: str) -> ApiResponse:
        """
        Authorize or deny device (user consent).

        Handles the user's authorization decision for the device flow.
        Called when the user approves or denies access on the device verification page.
        Requires user authentication via session cookie.

        Args:
            user_code: The user code entered by the user (e.g., WDJB-MJHT)
            action: User's authorization decision ('allow' or 'deny')

        Returns:
            ApiResponse with authorization result
        """
        return self._make_form_request(
            "/oauth/device/authorize",
            {"user_code": user_code, "action": action},
        )

    def oauth_authorize(
        self,
        client_id: str,
        redirect_uri: str,
        response_type: str = "code",
        scope: str | None = None,
        state: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> ApiResponse:
        """
        OAuth authorization endpoint (GET).

        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            response_type: Response type (must be 'code')
            scope: OAuth scope
            state: State parameter for CSRF protection
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE code challenge method (plain or S256)

        Returns:
            ApiResponse with authorization result
        """
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            **self._build_params(
                scope=scope,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
            ),
        }
        return self._make_request("GET", "/oauth/authorize", params=params)

    def oauth_consent(
        self,
        client_id: str,
        redirect_uri: str,
        action: str,
        scope: str | None = None,
        state: str | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> ApiResponse:
        """
        Handle OAuth authorization consent (POST).

        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI
            action: Consent action ('allow' or 'deny')
            scope: OAuth scope
            state: State parameter
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE code challenge method

        Returns:
            ApiResponse with consent result
        """
        form_data = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "action": action,
            **self._build_params(
                scope=scope,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
            ),
        }
        return self._make_form_request(
            "/oauth/authorize",
            form_data,
            raise_on_401=False,
            raise_on_5xx=False,
        )

    def oauth_token(
        self,
        grant_type: str,
        client_id: str,
        client_secret: str,
        code: str | None = None,
        redirect_uri: str | None = None,
        code_verifier: str | None = None,
        refresh_token: str | None = None,
        device_code: str | None = None,
        scope: str | None = None,
    ) -> ApiResponse:
        """
        OAuth token endpoint.

        Args:
            grant_type: OAuth grant type ('authorization_code', 'refresh_token',
                'client_credentials', or 'urn:ietf:params:oauth:grant-type:device_code')
            client_id: OAuth client ID
            client_secret: OAuth client secret
            code: Authorization code (required for authorization_code grant)
            redirect_uri: Redirect URI (required for authorization_code grant)
            code_verifier: PKCE code verifier (for PKCE flow)
            refresh_token: Refresh token (required for refresh_token grant)
            device_code: Device code (required for device_code grant)
            scope: Scope (optional for client_credentials grant)

        Returns:
            ApiResponse with token data
        """
        form_data: dict[str, str] = {
            "grant_type": grant_type,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        if grant_type == "authorization_code":
            form_data.update(
                self._build_params(
                    code=code,
                    redirect_uri=redirect_uri,
                    code_verifier=code_verifier,
                )
            )
        elif grant_type == "refresh_token":
            form_data.update(self._build_params(refresh_token=refresh_token))
        elif grant_type == "urn:ietf:params:oauth:grant-type:device_code":
            form_data.update(self._build_params(device_code=device_code))
        elif grant_type == "client_credentials":
            form_data.update(self._build_params(scope=scope))

        return self._make_form_request(
            "/oauth/token",
            form_data,
            error_key="error_description",
            fallback_error_key="error",
        )


def create_authenticated_client(
    email: str, password: str, base_url: str = "http://localhost:8000/api"
) -> TaskManagerClient:
    """
    Create and authenticate a TaskManager client using session-based login.

    Args:
        email: Email for authentication
        password: Password for authentication
        base_url: Base URL for the TaskManager API

    Returns:
        Authenticated TaskManagerClient instance

    Raises:
        AuthenticationError: If authentication fails
    """
    client = TaskManagerClient(base_url)
    response = client.login(email, password)

    if not response.success:
        raise AuthenticationError(f"Authentication failed: {response.error}")

    return client


def create_client_credentials_client(
    client_id: str, client_secret: str, base_url: str = "http://localhost:8000/api"
) -> TaskManagerClient:
    """
    Create and authenticate a TaskManager client using OAuth2 Client Credentials.

    This is the recommended approach for server-to-server (S2S) authentication.
    The client will automatically obtain an access token using the client credentials
    grant type and use it for all subsequent API requests.

    Args:
        client_id: OAuth client ID
        client_secret: OAuth client secret
        base_url: Base URL for the TaskManager API

    Returns:
        Authenticated TaskManagerClient instance with Bearer token auth

    Raises:
        AuthenticationError: If client credentials authentication fails
    """
    import time

    # Create an unauthenticated client first to get the token
    session = requests.Session()

    # Make token request
    token_url = f"{base_url.rstrip('/')}/oauth/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        response = session.post(
            token_url,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code == 401:
            raise AuthenticationError("Invalid client credentials")

        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get(
                    "error_description", error_data.get("error", "Unknown error")
                )
            except (ValueError, requests.exceptions.JSONDecodeError):
                error_msg = f"HTTP {response.status_code}: {response.text}"
            raise AuthenticationError(f"Client credentials auth failed: {error_msg}")

        token_response = response.json()
        access_token = token_response.get("access_token")

        if not access_token:
            raise AuthenticationError("No access token in response")

        # Create client with the access token
        client = TaskManagerClient(base_url, access_token=access_token)

        # Store token expiration for potential refresh logic
        expires_in = token_response.get("expires_in", 3600)
        client.token_expires_at = time.time() + expires_in

        return client

    except requests.exceptions.RequestException as e:
        raise NetworkError(f"Network error during authentication: {e}") from e
