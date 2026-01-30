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
            if method.upper() == "GET":
                response = self.session.get(
                    url, params=params, cookies=self.cookies, headers=headers
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, json=data, params=params, cookies=self.cookies, headers=headers
                )
            elif method.upper() == "PUT":
                response = self.session.put(
                    url, json=data, params=params, cookies=self.cookies, headers=headers
                )
            elif method.upper() == "DELETE":
                response = self.session.delete(
                    url, params=params, cookies=self.cookies, headers=headers
                )
            else:
                return ApiResponse(
                    success=False, error=f"Unsupported HTTP method: {method}"
                )

            # Handle cookie authentication
            if "set-cookie" in response.headers:
                split_cookie = response.headers["set-cookie"].split("=", 1)
                if len(split_cookie) == 2:
                    self.cookies[split_cookie[0]] = split_cookie[1].split(";")[0]

            # Handle error status codes with appropriate exceptions
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    # FastAPI format: {"detail": {"code": "...", "message": "...", "details": {...}}}
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

    # Authentication methods
    def login(self, username: str, password: str) -> ApiResponse:
        """
        Authenticate user with username and password.

        Args:
            username: User's username
            password: User's password

        Returns:
            ApiResponse with authentication result
        """
        return self._make_request(
            "POST", "/auth/login", {"username": username, "password": password}
        )

    def register(self, username: str, email: str, password: str) -> ApiResponse:
        """
        Register a new user account.

        Args:
            username: Desired username
            email: User's email address
            password: User's password

        Returns:
            ApiResponse with registration result
        """
        return self._make_request(
            "POST",
            "/auth/register",
            {"username": username, "email": email, "password": password},
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
        self, name: str, description: str | None = None, color: str | None = None
    ) -> ApiResponse:
        """
        Create a new project.

        Args:
            name: Project name
            description: Optional project description
            color: Optional project color (hex format: #RRGGBB)

        Returns:
            ApiResponse with created project data
        """
        data: dict[str, str] = {"name": name}
        if description is not None:
            data["description"] = description
        if color is not None:
            data["color"] = color
        return self._make_request("POST", "/projects", data)

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
        data = {}
        if name is not None:
            data["name"] = name
        if color is not None:
            data["color"] = color
        if description is not None:
            data["description"] = description
        return self._make_request("PUT", f"/projects/{project_id}", data)

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
        limit: int | None = None,
        include_subtasks: bool = False,
    ) -> ApiResponse:
        """
        Get todos with optional filtering.

        Args:
            project_id: Filter by project ID
            status: Filter by status (pending, in_progress, completed, cancelled, overdue, all)
            start_date: Filter tasks with due_date on or after this date (ISO format)
            end_date: Filter tasks with due_date on or before this date (ISO format)
            category: Filter by category name (project name)
            limit: Maximum number of tasks to return
            include_subtasks: Include subtasks in the response (default: False)

        Returns:
            ApiResponse with TaskListResponse data
        """
        params: dict[str, str | int | bool] = {}
        if project_id is not None:
            params["project_id"] = project_id
        if status is not None:
            params["status"] = status
        if start_date is not None:
            params["start_date"] = start_date
        if end_date is not None:
            params["end_date"] = end_date
        if category is not None:
            params["category"] = category
        if limit is not None:
            params["limit"] = limit
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
            tags: list of tags
            parent_id: Parent todo ID to create a subtask (optional)

        Returns:
            ApiResponse with TaskCreateResponse data
        """
        data: dict[str, str | int | float | list[str]] = {"title": title}
        if project_id is not None:
            data["project_id"] = project_id
        if description is not None:
            data["description"] = description
        if category is not None:
            data["category"] = category
        if priority is not None:
            data["priority"] = priority
        if estimated_hours is not None:
            data["estimated_hours"] = estimated_hours
        if due_date is not None:
            data["due_date"] = due_date
        if tags is not None:
            data["tags"] = tags
        if parent_id is not None:
            data["parent_id"] = parent_id
        return self._make_request("POST", "/todos", data)

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
        tags: list[str] | None = None,
        parent_id: int | None = None,
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
            tags: New tags list
            parent_id: New parent ID to move task (optional)

        Returns:
            ApiResponse with TaskUpdateResponse data
        """
        data: dict[str, float | str | int | list[str]] = {}
        if title is not None:
            data["title"] = title
        if description is not None:
            data["description"] = description
        if category is not None:
            data["category"] = category
        if priority is not None:
            data["priority"] = priority
        if estimated_hours is not None:
            data["estimated_hours"] = estimated_hours
        if actual_hours is not None:
            data["actual_hours"] = actual_hours
        if status is not None:
            data["status"] = status
        if due_date is not None:
            data["due_date"] = due_date
        if tags is not None:
            data["tags"] = tags
        if parent_id is not None:
            data["parent_id"] = parent_id
        return self._make_request("PUT", f"/todos/{todo_id}", data)

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
        data: dict[str, float] = {}
        if actual_hours is not None:
            data["actual_hours"] = actual_hours
        return self._make_request("POST", f"/todos/{todo_id}/complete", data)

    def get_attachments(self, todo_id: int) -> ApiResponse:
        """
        Get all attachments for a todo.

        Args:
            todo_id: Todo ID

        Returns:
            ApiResponse with list of attachments
        """
        return self._make_request("GET", f"/todos/{todo_id}/attachments")

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
        params: dict[str, str] = {"query": query}
        if category is not None:
            params["category"] = category
        return self._make_request("GET", "/tasks/search", params=params)

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
        data: dict[str, str | list[str]] = {"name": name, "redirectUris": redirect_uris}
        if grant_types is not None:
            data["grantTypes"] = grant_types
        if scopes is not None:
            data["scopes"] = scopes
        if token_endpoint_auth_method is not None:
            data["token_endpoint_auth_method"] = token_endpoint_auth_method
        return self._make_request("POST", "/oauth/clients", data)

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
        data: dict[str, str | list[str]] = {"name": name, "redirectUris": redirect_uris}
        if grant_types is not None:
            data["grantTypes"] = grant_types
        if scopes is not None:
            data["scopes"] = scopes
        if token_endpoint_auth_method is not None:
            data["token_endpoint_auth_method"] = token_endpoint_auth_method
        return self._make_request("POST", "/oauth/clients/system", data)

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
        data: dict[str, str | list[str]] = {"name": name, "redirectUris": redirect_uris}
        if grant_types is not None:
            data["grantTypes"] = grant_types
        if scopes is not None:
            data["scopes"] = scopes
        return self._make_request("PUT", f"/oauth/clients/{client_id}", data)

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
        data: dict[str, str] = {"client_id": client_id}
        if scope is not None:
            data["scope"] = scope

        # Device code endpoint uses form encoding
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.session.post(
                f"{self.base_url}/oauth/device/code", data=data, headers=headers
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get(
                        "error_description",
                        error_data.get("error", f"HTTP {response.status_code}"),
                    )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                if response.status_code == 401:
                    raise AuthenticationError(error_message)
                elif response.status_code >= 500:
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
        data = {"user_code": user_code, "action": action}

        # Device authorize endpoint uses form encoding
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.session.post(
                f"{self.base_url}/oauth/device/authorize",
                data=data,
                headers=headers,
                cookies=self.cookies,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get(
                        "error", f"HTTP {response.status_code}"
                    )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                if response.status_code == 401:
                    raise AuthenticationError(error_message)
                elif response.status_code >= 500:
                    raise ServerError(error_message)

                return ApiResponse(
                    success=False, error=error_message, status_code=response.status_code
                )

            return ApiResponse(success=True, status_code=response.status_code)

        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e)) from e

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
        }
        if scope is not None:
            params["scope"] = scope
        if state is not None:
            params["state"] = state
        if code_challenge is not None:
            params["code_challenge"] = code_challenge
        if code_challenge_method is not None:
            params["code_challenge_method"] = code_challenge_method

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
        data = {"client_id": client_id, "redirect_uri": redirect_uri, "action": action}
        if scope is not None:
            data["scope"] = scope
        if state is not None:
            data["state"] = state
        if code_challenge is not None:
            data["code_challenge"] = code_challenge
        if code_challenge_method is not None:
            data["code_challenge_method"] = code_challenge_method

        # Use form encoding for OAuth consent
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.session.post(
                f"{self.base_url}/oauth/authorize",
                data=data,
                headers=headers,
                cookies=self.cookies,
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get(
                        "error", f"HTTP {response.status_code}"
                    )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                return ApiResponse(
                    success=False, error=error_message, status_code=response.status_code
                )

            return ApiResponse(success=True, status_code=response.status_code)

        except requests.exceptions.RequestException as e:
            raise NetworkError(str(e)) from e

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
        data = {
            "grant_type": grant_type,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        if grant_type == "authorization_code":
            if code is not None:
                data["code"] = code
            if redirect_uri is not None:
                data["redirect_uri"] = redirect_uri
            if code_verifier is not None:
                data["code_verifier"] = code_verifier
        elif grant_type == "refresh_token":
            if refresh_token is not None:
                data["refresh_token"] = refresh_token
        elif grant_type == "urn:ietf:params:oauth:grant-type:device_code":
            if device_code is not None:
                data["device_code"] = device_code
        elif grant_type == "client_credentials":
            if scope is not None:
                data["scope"] = scope

        # OAuth token endpoint uses form encoding
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.session.post(
                f"{self.base_url}/oauth/token", data=data, headers=headers
            )

            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get(
                        "error_description",
                        error_data.get("error", f"HTTP {response.status_code}"),
                    )
                except (ValueError, requests.exceptions.JSONDecodeError):
                    error_message = f"HTTP {response.status_code}: {response.text}"

                if response.status_code == 401:
                    raise AuthenticationError(error_message)
                elif response.status_code >= 500:
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


def create_authenticated_client(
    username: str, password: str, base_url: str = "http://localhost:8000/api"
) -> TaskManagerClient:
    """
    Create and authenticate a TaskManager client using session-based login.

    Args:
        username: Username for authentication
        password: Password for authentication
        base_url: Base URL for the TaskManager API

    Returns:
        Authenticated TaskManagerClient instance

    Raises:
        AuthenticationError: If authentication fails
    """
    client = TaskManagerClient(base_url)
    response = client.login(username, password)

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
