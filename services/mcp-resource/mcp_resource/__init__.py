"""MCP Resource Server Package.

OAuth-protected MCP resource server for TaskManager integration.
"""

from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.security import (
    LakeraGuardError,
    guard_content,
    guard_tool,
    is_content_flagged,
    screen_content,
)
from taskmanager_sdk import (
    ApiResponse,
    TaskManagerClient,
    create_authenticated_client,
)

# Backwards compatibility alias
TaskManagerAPI = TaskManagerClient

__all__ = [
    "ApiResponse",
    "TaskManagerAPI",
    "TaskManagerClient",
    "create_authenticated_client",
    "IntrospectionTokenVerifier",
    # Lakera Guard security
    "LakeraGuardError",
    "guard_content",
    "guard_tool",
    "is_content_flagged",
    "screen_content",
]

__version__ = "0.1.0"
