"""MCP Resource Server Package.

OAuth-protected MCP resource server for TaskManager integration.
"""

from taskmanager_sdk import (
    ApiResponse,
    TaskManagerClient,
    create_authenticated_client,
)

from .token_verifier import IntrospectionTokenVerifier

# Backwards compatibility alias
TaskManagerAPI = TaskManagerClient

__all__ = [
    "ApiResponse",
    "TaskManagerAPI",
    "TaskManagerClient",
    "create_authenticated_client",
    "IntrospectionTokenVerifier",
]

__version__ = "0.1.0"
