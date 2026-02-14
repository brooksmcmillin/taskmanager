"""CSRF protection middleware.

Validates Origin/Referer headers on state-changing requests that use
session cookie authentication. This provides defense-in-depth on top
of SameSite=Lax cookies.

Requests using Bearer tokens or API keys are not vulnerable to CSRF
and are skipped.
"""

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate Origin header on session-authenticated state-changing requests."""

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        super().__init__(app)
        self.allowed_origins = set(allowed_origins)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip safe methods
        if request.method in SAFE_METHODS:
            return await call_next(request)

        # Skip if using Bearer token or API key (not CSRF-vulnerable)
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)
        if request.headers.get("x-api-key"):
            return await call_next(request)

        # Only enforce CSRF for session-cookie-authenticated requests
        if "session" not in request.cookies:
            return await call_next(request)

        # Validate Origin or Referer
        origin = request.headers.get("origin")
        if origin:
            if origin not in self.allowed_origins:
                return self._csrf_error()
            return await call_next(request)

        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if not parsed.scheme or not parsed.netloc:
                return self._csrf_error()
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if referer_origin not in self.allowed_origins:
                return self._csrf_error()
            return await call_next(request)

        # No Origin or Referer header present.
        # SameSite=Lax is the primary defense; allow the request through
        # since legitimate same-origin requests may omit these headers.
        return await call_next(request)

    def _csrf_error(self) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={
                "detail": {
                    "code": "CSRF_001",
                    "message": "CSRF validation failed: origin not allowed",
                }
            },
        )
