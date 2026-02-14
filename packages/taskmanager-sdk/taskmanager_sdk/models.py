from dataclasses import dataclass
from typing import Any


@dataclass
class ApiResponse:
    """Response object for all API calls."""

    success: bool
    data: Any | None = None
    error: str | None = None
    status_code: int | None = None


@dataclass
class User:
    """User model."""

    id: int
    email: str


@dataclass
class Project:
    """Project model."""

    id: int
    name: str
    color: str
    description: str | None
    created_at: str
    updated_at: str
    user_id: int


@dataclass
class Todo:
    """Todo model."""

    id: int
    title: str
    description: str | None
    priority: str
    estimated_hours: float
    actual_hours: float | None
    status: str
    due_date: str | None
    tags: list[str] | None
    created_at: str
    updated_at: str
    completed_at: str | None
    user_id: int
    project_id: int | None


@dataclass
class OAuthClient:
    """OAuth client model."""

    id: int
    name: str
    client_id: str
    redirect_uris: list[str]
    grant_types: list[str]
    scopes: list[str]
    is_active: bool
    created_at: str


@dataclass
class OAuthToken:
    """OAuth token response model."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    scope: str | None = None


@dataclass
class OAuthError:
    """OAuth error response model."""

    error: str
    error_description: str | None = None


@dataclass
class DeviceAuthorizationResponse:
    """Response from the device authorization endpoint (RFC 8628)."""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int
    verification_uri_complete: str | None = None


@dataclass
class Comment:
    """Comment on a task."""

    id: int
    todo_id: int
    user_id: int
    content: str
    created_at: str
    updated_at: str | None = None


@dataclass
class Task:
    """Task object returned by API endpoints."""

    id: int
    title: str
    status: str
    priority: str
    description: str | None = None
    due_date: str | None = None
    category: str | None = None
    project_name: str | None = None
    project_color: str | None = None
    tags: list[str] | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class TaskListResponse:
    """Response containing a list of tasks."""

    tasks: list[Task]


@dataclass
class TaskCreateResponse:
    """Response from creating a task."""

    id: int
    title: str
    status: str


@dataclass
class TaskUpdateResponse:
    """Response from updating a task."""

    id: int
    updated_fields: list[str]
    status: str


@dataclass
class TaskSearchResponse:
    """Response from searching tasks."""

    tasks: list[Task]
    count: int


@dataclass
class Category:
    """Category with task count."""

    name: str
    task_count: int


@dataclass
class CategoryListResponse:
    """Response containing a list of categories."""

    categories: list[Category]
