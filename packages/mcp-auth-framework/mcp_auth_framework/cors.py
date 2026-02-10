"""CORS origin validation for MCP OAuth endpoints."""

import os

from starlette.requests import Request


def parse_allowed_origins(env_var: str = "ALLOWED_MCP_ORIGINS") -> list[str]:
    """Parse allowed CORS origins from a comma-separated environment variable.

    Args:
        env_var: Name of the environment variable to read.

    Returns:
        List of allowed origin strings, stripped of whitespace.
    """
    raw = os.getenv(env_var, "")
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_cors_origin(request: Request, allowed_origins: list[str]) -> str:
    """Get CORS origin header value based on request origin.

    Only returns the origin if it's in the allowed list, otherwise returns
    empty string to deny CORS access.

    Args:
        request: The incoming request.
        allowed_origins: List of allowed origin strings.

    Returns:
        Origin value for Access-Control-Allow-Origin header.
    """
    request_origin = request.headers.get("origin", "")
    if request_origin in allowed_origins:
        return request_origin
    return ""


def build_cors_headers(request: Request, allowed_origins: list[str]) -> dict[str, str]:
    """Build standard CORS headers for OAuth discovery endpoints.

    Args:
        request: The incoming request.
        allowed_origins: List of allowed origin strings.

    Returns:
        Dict of CORS headers.
    """
    return {
        "Access-Control-Allow-Origin": get_cors_origin(request, allowed_origins),
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }
