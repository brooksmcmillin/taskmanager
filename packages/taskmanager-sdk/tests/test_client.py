"""Tests for TaskManagerClient."""

from unittest.mock import Mock

import pytest
import requests
from taskmanager_sdk import TaskManagerClient, create_authenticated_client
from taskmanager_sdk.exceptions import (
    AuthenticationError,
    AuthorizationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class TestClientInitialization:
    """Test client initialization."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default parameters."""
        client = TaskManagerClient()
        assert client.base_url == "http://localhost:4321/api"
        assert isinstance(client.session, requests.Session)

    def test_init_with_custom_url(self) -> None:
        """Test client initialization with custom URL."""
        url = "https://api.example.com"
        client = TaskManagerClient(url)
        assert client.base_url == url

    def test_init_strips_trailing_slash(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = TaskManagerClient("http://localhost:4321/api/")
        assert client.base_url == "http://localhost:4321/api"

    def test_init_with_custom_session(self, mock_session: Mock) -> None:
        """Test client initialization with custom session."""
        client = TaskManagerClient(session=mock_session)
        assert client.session == mock_session


class TestAuthentication:
    """Test authentication methods."""

    def test_login_success(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_user: dict[str, str | int],
    ) -> None:
        """Test successful login."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True, "user": sample_user}
        mock_session.post.return_value = mock_response

        result = client.login("testuser", "password123")

        assert result.success is True
        assert result.data == {"success": True, "user": sample_user}
        mock_session.post.assert_called_once()

    def test_login_failure(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test failed login."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Invalid credentials"}
        mock_session.post.return_value = mock_response

        with pytest.raises(AuthenticationError):
            client.login("testuser", "wrongpassword")

    def test_register_success(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test successful registration."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {
            "success": True,
            "message": "User created successfully",
            "userId": 1,
        }
        mock_session.post.return_value = mock_response

        result = client.register("newuser", "new@example.com", "password123")

        assert result.success is True
        assert result.data is not None
        assert result.data["userId"] == 1

    def test_logout_success(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test successful logout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.post.return_value = mock_response

        result = client.logout()

        assert result.success is True

    def test_create_authenticated_client(
        self, mock_session: Mock, sample_user: dict[str, str | int]
    ) -> None:
        """Test create_authenticated_client helper function."""
        from unittest.mock import patch

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True, "user": sample_user}

        with patch("taskmanager_sdk.client.requests.Session") as mock_session_class:
            mock_session_class.return_value = mock_session
            mock_session.post.return_value = mock_response

            client = create_authenticated_client("testuser", "password123")
            assert isinstance(client, TaskManagerClient)


class TestProjects:
    """Test project management methods."""

    def test_get_projects(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_project: dict[str, str | int],
    ) -> None:
        """Test getting list of projects."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = [sample_project]
        mock_session.get.return_value = mock_response

        result = client.get_projects()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Test Project"

    def test_create_project(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test creating a project."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_session.post.return_value = mock_response

        result = client.create_project(
            name="New Project", description="A new project", color="#FF5733"
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["id"] == 1

    def test_create_project_minimal(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test creating a project with only required fields."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_session.post.return_value = mock_response

        result = client.create_project(name="New Project")

        assert result.success is True
        mock_session.post.assert_called_once()

        # Verify only name is in the data
        call_args = mock_session.post.call_args
        assert call_args.kwargs["json"] == {"name": "New Project"}

    def test_get_project(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_project: dict[str, str | int],
    ) -> None:
        """Test getting a specific project."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = sample_project
        mock_session.get.return_value = mock_response

        result = client.get_project(1)

        assert result.success is True
        assert result.data is not None
        assert result.data["id"] == 1

    def test_update_project(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test updating a project."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.put.return_value = mock_response

        result = client.update_project(1, name="Updated Project")

        assert result.success is True

    def test_delete_project(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test deleting a project."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.delete.return_value = mock_response

        result = client.delete_project(1)

        assert result.success is True


class TestTodos:
    """Test todo management methods."""

    def test_get_todos(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_todo: dict[str, str | int | float | list[str] | None],
    ) -> None:
        """Test getting list of todos."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = [sample_todo]
        mock_session.get.return_value = mock_response

        result = client.get_todos()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["title"] == "Test Todo"

    def test_get_todos_with_filters(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test getting todos with filters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"tasks": []}
        mock_session.get.return_value = mock_response

        result = client.get_todos(
            project_id=1,
            status="completed",
            start_date="2025-01-01",
            end_date="2025-12-31",
            category="Work",
            limit=10,
        )

        assert result.success is True
        mock_session.get.assert_called_once()

        # Verify filters were passed as params
        call_args = mock_session.get.call_args
        assert call_args.kwargs["params"]["project_id"] == 1
        assert call_args.kwargs["params"]["status"] == "completed"
        assert call_args.kwargs["params"]["start_date"] == "2025-01-01"
        assert call_args.kwargs["params"]["end_date"] == "2025-12-31"
        assert call_args.kwargs["params"]["category"] == "Work"
        assert call_args.kwargs["params"]["limit"] == 10

    def test_create_todo(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test creating a todo."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_session.post.return_value = mock_response

        result = client.create_todo(
            title="New Todo",
            description="A new todo",
            priority="high",
            estimated_hours=3.5,
            tags=["urgent"],
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["id"] == 1

    def test_create_todo_minimal(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test creating a todo with only required fields."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {"id": 1}
        mock_session.post.return_value = mock_response

        result = client.create_todo(title="New Todo")

        assert result.success is True

    def test_get_todo(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_todo: dict[str, str | int | float | list[str] | None],
    ) -> None:
        """Test getting a specific todo."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = sample_todo
        mock_session.get.return_value = mock_response

        result = client.get_todo(1)

        assert result.success is True
        assert result.data is not None
        assert result.data["id"] == 1

    def test_update_todo(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test updating a todo."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.put.return_value = mock_response

        result = client.update_todo(
            1, title="Updated Todo", status="in_progress", actual_hours=2.0
        )

        assert result.success is True

    def test_delete_todo(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test deleting a todo."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.delete.return_value = mock_response

        result = client.delete_todo(1)

        assert result.success is True

    def test_complete_todo(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test completing a todo with actual hours."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.post.return_value = mock_response

        result = client.complete_todo(1, actual_hours=3.5)

        assert result.success is True
        call_args = mock_session.post.call_args
        assert call_args.kwargs["json"]["actual_hours"] == 3.5

    def test_complete_todo_without_hours(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test completing a todo without specifying actual hours."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"success": True}
        mock_session.post.return_value = mock_response

        result = client.complete_todo(1)

        assert result.success is True
        call_args = mock_session.post.call_args
        assert call_args.kwargs["json"] == {}

    def test_create_todo_with_category(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test creating a todo with category."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {
            "id": 1,
            "title": "New Todo",
            "status": "created",
        }
        mock_session.post.return_value = mock_response

        result = client.create_todo(title="New Todo", category="Work", priority="high")

        assert result.success is True
        call_args = mock_session.post.call_args
        assert call_args.kwargs["json"]["category"] == "Work"

    def test_update_todo_with_category(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test updating a todo with category."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "id": 1,
            "updated_fields": ["category"],
            "status": "updated",
        }
        mock_session.put.return_value = mock_response

        result = client.update_todo(1, category="Personal")

        assert result.success is True
        call_args = mock_session.put.call_args
        assert call_args.kwargs["json"]["category"] == "Personal"

    def test_search_tasks(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test searching tasks."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "tasks": [
                {
                    "id": 1,
                    "title": "Test Todo",
                    "status": "pending",
                    "priority": "medium",
                }
            ],
            "count": 1,
        }
        mock_session.get.return_value = mock_response

        result = client.search_tasks("test")

        assert result.success is True
        assert result.data is not None
        assert result.data["count"] == 1
        assert len(result.data["tasks"]) == 1

    def test_search_tasks_with_category(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test searching tasks with category filter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {"tasks": [], "count": 0}
        mock_session.get.return_value = mock_response

        result = client.search_tasks("test", category="Work")

        assert result.success is True
        call_args = mock_session.get.call_args
        assert call_args.kwargs["params"]["query"] == "test"
        assert call_args.kwargs["params"]["category"] == "Work"


class TestCategories:
    """Test category methods."""

    def test_get_categories(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test getting list of categories."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "categories": [
                {"name": "Work", "task_count": 5},
                {"name": "Personal", "task_count": 3},
            ]
        }
        mock_session.get.return_value = mock_response

        result = client.get_categories()

        assert result.success is True
        assert result.data is not None
        assert len(result.data["categories"]) == 2
        assert result.data["categories"][0]["name"] == "Work"
        assert result.data["categories"][0]["task_count"] == 5


class TestOAuth:
    """Test OAuth methods."""

    def test_get_oauth_clients(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_oauth_client: dict[str, str | int | bool | list[str]],
    ) -> None:
        """Test getting list of OAuth clients."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = [sample_oauth_client]
        mock_session.get.return_value = mock_response

        result = client.get_oauth_clients()

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 1
        assert result.data[0]["name"] == "Test OAuth Client"

    def test_create_oauth_client(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_oauth_client: dict[str, str | int | bool | list[str]],
    ) -> None:
        """Test creating an OAuth client."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.headers = {}
        mock_response.json.return_value = {
            **sample_oauth_client,
            "client_secret": "test_secret",
        }
        mock_session.post.return_value = mock_response

        result = client.create_oauth_client(
            name="New OAuth Client",
            redirect_uris=["http://localhost:3000/callback"],
            grant_types=["authorization_code"],
            scopes=["read", "write"],
        )

        assert result.success is True
        assert result.data is not None
        assert "client_secret" in result.data

    def test_get_jwks(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test getting JWKS."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": "test_key_id",
                    "alg": "RS256",
                    "n": "test_n",
                    "e": "AQAB",
                }
            ]
        }
        mock_session.get.return_value = mock_response

        result = client.get_jwks()

        assert result.success is True
        assert result.data is not None
        assert "keys" in result.data
        assert len(result.data["keys"]) == 1

    def test_oauth_authorize(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test OAuth authorization endpoint."""
        mock_response = Mock()
        mock_response.status_code = 302
        mock_response.headers = {}
        mock_response.json.return_value = {}
        mock_session.get.return_value = mock_response

        result = client.oauth_authorize(
            client_id="test_client",
            redirect_uri="http://localhost:3000/callback",
            response_type="code",
            scope="read",
            state="test_state",
        )

        assert result.success is True

    def test_oauth_token(
        self,
        client: TaskManagerClient,
        mock_session: Mock,
        sample_oauth_token: dict[str, str | int],
    ) -> None:
        """Test OAuth token endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = sample_oauth_token
        mock_session.post.return_value = mock_response

        result = client.oauth_token(
            grant_type="authorization_code",
            client_id="test_client",
            client_secret="test_secret",
            code="test_code",
            redirect_uri="http://localhost:3000/callback",
        )

        assert result.success is True
        assert result.data is not None
        assert result.data["access_token"] == "test_access_token"


class TestErrorHandling:
    """Test error handling."""

    def test_401_raises_authentication_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 401 status raises AuthenticationError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_session.get.return_value = mock_response

        with pytest.raises(AuthenticationError):
            client.get_projects()

    def test_403_raises_authorization_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 403 status raises AuthorizationError."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Forbidden"}
        mock_session.get.return_value = mock_response

        with pytest.raises(AuthorizationError):
            client.get_projects()

    def test_404_raises_not_found_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 404 status raises NotFoundError."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Not found"}
        mock_session.get.return_value = mock_response

        with pytest.raises(NotFoundError):
            client.get_project(999)

    def test_400_raises_validation_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 400 status raises ValidationError."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Invalid request"}
        mock_session.post.return_value = mock_response

        with pytest.raises(ValidationError):
            client.create_project(name="")

    def test_429_raises_rate_limit_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 429 status raises RateLimitError."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_session.get.return_value = mock_response

        with pytest.raises(RateLimitError):
            client.get_projects()

    def test_500_raises_server_error(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that 500 status raises ServerError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_session.get.return_value = mock_response

        with pytest.raises(ServerError):
            client.get_projects()

    def test_network_error(self, client: TaskManagerClient, mock_session: Mock) -> None:
        """Test that network errors raise NetworkError."""
        mock_session.get.side_effect = requests.exceptions.ConnectionError(
            "Connection failed"
        )

        with pytest.raises(NetworkError):
            client.get_projects()

    def test_cookie_handling(
        self, client: TaskManagerClient, mock_session: Mock
    ) -> None:
        """Test that cookies are properly handled."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"set-cookie": "session=abc123; Path=/; HttpOnly"}
        mock_response.json.return_value = {"success": True}
        mock_session.post.return_value = mock_response

        result = client.login("testuser", "password123")

        assert result.success is True
        assert "session" in client.cookies
        assert client.cookies["session"] == "abc123"
