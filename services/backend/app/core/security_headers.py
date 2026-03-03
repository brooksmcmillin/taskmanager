"""HTTP security headers middleware.

Adds security-related HTTP response headers to all responses to protect
against common web vulnerabilities.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Content-Security-Policy for the API (JSON-only responses, no HTML rendering)
# 'none' for all directives since the API does not serve HTML content.
API_CSP = "default-src 'none'"

# Permissions-Policy: disable all browser features not needed by the API
API_PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), usb=()"
)

# Strict-Transport-Security: 1 year, include subdomains
HSTS_VALUE = "max-age=31536000; includeSubDomains"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add HTTP security headers to every response.

    Headers added:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: default-src 'none'
    - Permissions-Policy: restrictive policy
    - Strict-Transport-Security: max-age=31536000; includeSubDomains (production only)
    """

    def __init__(self, app: ASGIApp, is_production: bool = False) -> None:
        super().__init__(app)
        self.is_production = is_production

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = API_CSP
        response.headers["Permissions-Policy"] = API_PERMISSIONS_POLICY

        if self.is_production:
            response.headers["Strict-Transport-Security"] = HSTS_VALUE

        return response
