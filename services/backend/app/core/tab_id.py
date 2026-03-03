"""Middleware to propagate X-Tab-Id header to a ContextVar.

The tab ID lets the frontend distinguish "my own change" from "external change"
so it can skip toasts for its own mutations. The ContextVar is read by get_db()
which sets it as a PG session variable via SET LOCAL.
"""

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

tab_id_var: ContextVar[str] = ContextVar("tab_id_var", default="")


class TabIdMiddleware(BaseHTTPMiddleware):
    """Read X-Tab-Id request header and store in a ContextVar."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        raw = request.headers.get("x-tab-id", "")
        # Sanitize: only keep alphanumeric/hyphen, max 8 chars
        valid = raw.isalnum() or all(
            c.isalnum() or c == "-" for c in raw
        )
        tab_id = raw[:8] if valid else ""
        token = tab_id_var.set(tab_id)
        try:
            return await call_next(request)
        finally:
            tab_id_var.reset(token)
