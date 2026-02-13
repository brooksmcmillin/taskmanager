"""Tests for TaskManager SDK models."""

from taskmanager_sdk.models import (
    ApiResponse,
    OAuthClient,
    OAuthError,
    OAuthToken,
    Project,
    Todo,
    User,
)


class TestApiResponse:
    """Test ApiResponse model."""

    def test_success_response(self) -> None:
        """Test creating a successful API response."""
        response = ApiResponse(success=True, data={"id": 1})
        assert response.success is True
        assert response.data == {"id": 1}
        assert response.error is None
        assert response.status_code is None

    def test_error_response(self) -> None:
        """Test creating an error API response."""
        response = ApiResponse(
            success=False, error="Something went wrong", status_code=400
        )
        assert response.success is False
        assert response.error == "Something went wrong"
        assert response.status_code == 400
        assert response.data is None

    def test_response_with_status_code(self) -> None:
        """Test API response with status code."""
        response = ApiResponse(success=True, data=None, status_code=200)
        assert response.status_code == 200


class TestUser:
    """Test User model."""

    def test_user_creation(self, sample_user: dict[str, str | int]) -> None:
        """Test creating a User instance."""
        user = User(**sample_user)  # type: ignore[arg-type]
        assert user.id == 1
        assert user.email == "test@example.com"

    def test_user_type_hints(self) -> None:
        """Test User type annotations."""
        user = User(id=1, email="test@example.com")
        assert isinstance(user.id, int)
        assert isinstance(user.email, str)


class TestProject:
    """Test Project model."""

    def test_project_creation(self, sample_project: dict[str, str | int]) -> None:
        """Test creating a Project instance."""
        project = Project(**sample_project)  # type: ignore[arg-type]
        assert project.id == 1
        assert project.name == "Test Project"
        assert project.color == "#FF5733"
        assert project.description == "A test project"
        assert project.user_id == 1

    def test_project_with_none_description(self) -> None:
        """Test creating a Project with None description."""
        project = Project(
            id=1,
            user_id=1,
            name="Test",
            color="#FF5733",
            description=None,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert project.description is None

    def test_project_type_hints(self) -> None:
        """Test Project type annotations."""
        project = Project(
            id=1,
            user_id=1,
            name="Test",
            color="#FF5733",
            description="Desc",
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
        )
        assert isinstance(project.id, int)
        assert isinstance(project.user_id, int)
        assert isinstance(project.name, str)
        assert isinstance(project.color, str)
        assert isinstance(project.created_at, str)
        assert isinstance(project.updated_at, str)


class TestTodo:
    """Test Todo model."""

    def test_todo_creation(
        self, sample_todo: dict[str, str | int | float | list[str] | None]
    ) -> None:
        """Test creating a Todo instance."""
        todo = Todo(**sample_todo)  # type: ignore[arg-type]
        assert todo.id == 1
        assert todo.title == "Test Todo"
        assert todo.status == "pending"
        assert todo.priority == "medium"
        assert todo.estimated_hours == 2.5
        assert todo.tags == ["test", "sample"]

    def test_todo_with_none_fields(self) -> None:
        """Test creating a Todo with None optional fields."""
        todo = Todo(
            id=1,
            user_id=1,
            project_id=None,
            title="Test",
            description=None,
            status="pending",
            priority="low",
            due_date=None,
            estimated_hours=0.0,
            actual_hours=None,
            tags=None,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            completed_at=None,
        )
        assert todo.project_id is None
        assert todo.description is None
        assert todo.actual_hours is None
        assert todo.tags is None
        assert todo.completed_at is None

    def test_todo_type_hints(self) -> None:
        """Test Todo type annotations."""
        todo = Todo(
            id=1,
            user_id=1,
            project_id=1,
            title="Test",
            description="Desc",
            status="pending",
            priority="medium",
            due_date="2025-12-31T23:59:59Z",
            estimated_hours=2.5,
            actual_hours=1.0,
            tags=["tag1"],
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:00:00Z",
            completed_at=None,
        )
        assert isinstance(todo.id, int)
        assert isinstance(todo.user_id, int)
        assert isinstance(todo.estimated_hours, (int, float))
        assert isinstance(todo.tags, list)


class TestOAuthClient:
    """Test OAuthClient model."""

    def test_oauth_client_creation(
        self, sample_oauth_client: dict[str, str | int | bool | list[str]]
    ) -> None:
        """Test creating an OAuthClient instance."""
        client = OAuthClient(**sample_oauth_client)  # type: ignore[arg-type]
        assert client.id == 1
        assert client.client_id == "test_client_id"
        assert client.name == "Test OAuth Client"
        assert client.redirect_uris == ["http://localhost:3000/callback"]
        assert client.grant_types == ["authorization_code"]
        assert client.scopes == ["read"]
        assert client.is_active is True

    def test_oauth_client_type_hints(self) -> None:
        """Test OAuthClient type annotations."""
        client = OAuthClient(
            id=1,
            client_id="test",
            name="Test",
            redirect_uris=["http://localhost"],
            grant_types=["authorization_code"],
            scopes=["read"],
            is_active=True,
            created_at="2025-01-01T00:00:00Z",
        )
        assert isinstance(client.redirect_uris, list)
        assert isinstance(client.grant_types, list)
        assert isinstance(client.scopes, list)
        assert isinstance(client.is_active, bool)


class TestOAuthToken:
    """Test OAuthToken model."""

    def test_oauth_token_creation(
        self, sample_oauth_token: dict[str, str | int]
    ) -> None:
        """Test creating an OAuthToken instance."""
        token = OAuthToken(**sample_oauth_token)  # type: ignore[arg-type]
        assert token.access_token == "test_access_token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.refresh_token == "test_refresh_token"
        assert token.scope == "read write"

    def test_oauth_token_minimal(self) -> None:
        """Test creating an OAuthToken with only required fields."""
        token = OAuthToken(access_token="test", token_type="Bearer", expires_in=3600)
        assert token.access_token == "test"
        assert token.refresh_token is None
        assert token.scope is None

    def test_oauth_token_type_hints(self) -> None:
        """Test OAuthToken type annotations."""
        token = OAuthToken(
            access_token="test",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="refresh",
            scope="read",
        )
        assert isinstance(token.access_token, str)
        assert isinstance(token.token_type, str)
        assert isinstance(token.expires_in, int)


class TestOAuthError:
    """Test OAuthError model."""

    def test_oauth_error_creation(self) -> None:
        """Test creating an OAuthError instance."""
        error = OAuthError(
            error="invalid_grant", error_description="The authorization code is invalid"
        )
        assert error.error == "invalid_grant"
        assert error.error_description == "The authorization code is invalid"

    def test_oauth_error_minimal(self) -> None:
        """Test creating an OAuthError with only required fields."""
        error = OAuthError(error="invalid_request")
        assert error.error == "invalid_request"
        assert error.error_description is None

    def test_oauth_error_type_hints(self) -> None:
        """Test OAuthError type annotations."""
        error = OAuthError(
            error="server_error", error_description="Server error occurred"
        )
        assert isinstance(error.error, str)
        assert isinstance(error.error_description, str)
