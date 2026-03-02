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
        "due_date": "2025-12-31",
        "deadline_type": "preferred",
        "estimated_hours": 2.5,
        "actual_hours": None,
        "tags": ["test", "sample"],
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
        "completed_at": None,
    }


@pytest.fixture
def sample_snippet() -> dict[str, str | int | list[str] | None]:
    """Sample snippet data."""
    return {
        "id": 1,
        "category": "standup",
        "title": "Daily standup notes",
        "content": "Worked on snippet feature",
        "snippet_date": "2026-02-28",
        "tags": ["dev", "daily"],
        "created_at": "2026-02-28T10:00:00Z",
        "updated_at": None,
    }


@pytest.fixture
def sample_article() -> dict[str, str | int | bool | list[str] | None]:
    """Sample news article data."""
    return {
        "id": 1,
        "title": "New Python Release",
        "url": "https://example.com/python-release",
        "summary": "Python 3.14 has been released.",
        "author": "Guido",
        "published_at": "2026-02-28T10:30:00+00:00",
        "keywords": ["python", "release"],
        "feed_source_name": "PythonNews",
        "is_read": False,
        "rating": None,
        "read_at": None,
    }


@pytest.fixture
def sample_feed_source() -> dict[str, str | int | float | bool | None]:
    """Sample feed source data."""
    return {
        "id": 1,
        "name": "PythonNews",
        "url": "https://pythonnews.com/feed.xml",
        "description": "Latest Python news",
        "type": "article",
        "is_active": True,
        "is_featured": False,
        "fetch_interval_hours": 6,
        "last_fetched_at": None,
        "quality_score": 1.0,
        "created_at": "2026-02-15T08:00:00+00:00",
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
