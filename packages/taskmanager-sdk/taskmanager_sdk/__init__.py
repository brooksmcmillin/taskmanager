"""
TaskManager SDK - Python client library for TaskManager API.

This SDK provides a clean, Pythonic interface for interacting with the TaskManager API,
including authentication, project management, todo management, reporting, and OAuth functionality.

Basic usage:
    >>> from taskmanager_sdk import TaskManagerClient, create_authenticated_client
    >>>
    >>> # Method 1: Create client and authenticate manually
    >>> client = TaskManagerClient("http://localhost:8000/api")
    >>> response = client.login("username", "password")
    >>>
    >>> # Method 2: Create pre-authenticated client (session-based)
    >>> client = create_authenticated_client("username", "password")
    >>>
    >>> # Method 3: Create client with OAuth2 Client Credentials (recommended for S2S)
    >>> from taskmanager_sdk import create_client_credentials_client
    >>> client = create_client_credentials_client("client_id", "client_secret")
    >>>
    >>> # Use the client
    >>> projects = client.get_projects()
    >>> todos = client.get_todos()
"""

__version__ = "0.2.0"
__author__ = "TaskManager SDK"

from .client import (
    TaskManagerClient,
    create_authenticated_client,
    create_client_credentials_client,
)
from .config import TokenConfig
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
    ServerError,
    TaskManagerError,
    ValidationError,
)
from .models import (
    ApiResponse,
    Category,
    CategoryListResponse,
    DeviceAuthorizationResponse,
    OAuthClient,
    OAuthError,
    OAuthToken,
    Project,
    Task,
    TaskCreateResponse,
    TaskListResponse,
    TaskSearchResponse,
    TaskUpdateResponse,
    Todo,
    User,
)

__all__ = [
    # Client classes
    "TaskManagerClient",
    # Configuration
    "TokenConfig",
    "create_authenticated_client",
    "create_client_credentials_client",
    # Models
    "ApiResponse",
    "Category",
    "CategoryListResponse",
    "DeviceAuthorizationResponse",
    "OAuthClient",
    "OAuthError",
    "OAuthToken",
    "Project",
    "Task",
    "TaskCreateResponse",
    "TaskListResponse",
    "TaskSearchResponse",
    "TaskUpdateResponse",
    "Todo",
    "User",
    # Exceptions
    "TaskManagerError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
]
