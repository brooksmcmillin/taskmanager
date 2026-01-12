"""
Centralized configuration constants for the MCP Auth server.

This module contains all token expiration times, timeouts, and other
configuration values.
"""


class TokenConfig:
    """Token and authentication timing configuration."""

    # Access token lifetime (1 hour)
    MCP_ACCESS_TOKEN_TTL_SECONDS: int = 3600

    # Authorization code lifetime (5 minutes)
    AUTHORIZATION_CODE_TTL_SECONDS: int = 300

    # Buffer time before token expiry to trigger refresh (5 minutes)
    TOKEN_REFRESH_BUFFER_SECONDS: int = 300

    # HTTP request timeout for external API calls
    HTTP_REQUEST_TIMEOUT_SECONDS: int = 30
