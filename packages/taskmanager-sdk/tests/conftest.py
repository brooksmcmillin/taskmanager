"""Pytest configuration and fixtures for TaskManager SDK tests."""

from unittest.mock import Mock

import pytest
import requests
from taskmanager_sdk import TaskManagerClient


@pytest.fixture
def base_url() -> str:
    """Base URL for testing."""
    return "http://localhost:4321/api"


@pytest.fixture
def mock_session() -> Mock:
    """Mock requests.Session for testing."""
    session = Mock(spec=requests.Session)
    session.headers = {}
    return session


@pytest.fixture
def client(base_url: str, mock_session: Mock) -> TaskManagerClient:
    """TaskManagerClient instance with mocked session."""
    client = TaskManagerClient(base_url, session=mock_session)
    return client


@pytest.fixture
def mock_response() -> Mock:
    """Mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.headers = {}
    response.json.return_value = {"success": True}
    return response


@pytest.fixture
def sample_user() -> dict[str, str | int]:
    """Sample user data."""
    return {"id": 1, "email": "test@example.com"}


@pytest.fixture
def sample_project() -> dict[str, str | int]:
    """Sample project data."""
    return {
        "id": 1,
        "user_id": 1,
        "name": "Test Project",
        "description": "A test project",
        "color": "#FF5733",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_todo() -> dict[str, str | int | float | list[str] | None]:
    """Sample todo data."""
    return {
        "id": 1,
        "user_id": 1,
        "project_id": 1,
        "title": "Test Todo",
        "description": "A test todo",
        "status": "pending",
        "priority": "medium",
        "due_date": "2025-12-31T23:59:59Z",
        "estimated_hours": 2.5,
        "actual_hours": None,
        "tags": ["test", "sample"],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "completed_at": None,
    }


@pytest.fixture
def sample_oauth_client() -> dict[str, str | int | bool | list[str]]:
    """Sample OAuth client data."""
    return {
        "id": 1,
        "client_id": "test_client_id",
        "name": "Test OAuth Client",
        "redirect_uris": ["http://localhost:3000/callback"],
        "grant_types": ["authorization_code"],
        "scopes": ["read"],
        "is_active": True,
        "created_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_oauth_token() -> dict[str, str | int]:
    """Sample OAuth token data."""
    return {
        "access_token": "test_access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "test_refresh_token",
        "scope": "read write",
    }
