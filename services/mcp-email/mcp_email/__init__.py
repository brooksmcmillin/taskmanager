"""MCP Email Server Package.

OAuth-protected MCP server for sending emails via FastMail.
"""

from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.security import (
    LakeraGuardError,
    guard_content,
    guard_tool,
    is_content_flagged,
    screen_content,
)

__all__ = [
    "IntrospectionTokenVerifier",
    # Lakera Guard security
    "LakeraGuardError",
    "guard_content",
    "guard_tool",
    "is_content_flagged",
    "screen_content",
]

__version__ = "0.1.0"
