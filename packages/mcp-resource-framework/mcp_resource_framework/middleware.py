"""ASGI middleware utilities for MCP resource servers."""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class NormalizePathMiddleware:
    """ASGI middleware to normalize paths so /mcp and /mcp/ work identically.

    Strips trailing slashes from all paths (except root) before routing.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        if scope["type"] == "http":
            path = scope.get("path", "/")
            # Normalize: strip trailing slash if path is not just "/"
            if path != "/" and path.endswith("/"):
                scope = dict(scope)
                scope["path"] = path.rstrip("/")
        await self.app(scope, receive, send)


def create_logging_middleware(
    app: Any, mask_auth: bool = True
) -> Callable[[dict[str, Any], Any, Any], Any]:
    """Create ASGI middleware to log detailed request information for debugging.

    Uses raw ASGI interface to avoid interfering with request body or streaming.

    Args:
        app: The ASGI application to wrap
        mask_auth: Whether to mask authorization header values (default: True)

    Returns:
        ASGI middleware function
    """

    async def middleware(scope: dict[str, Any], receive: Any, send: Any) -> Any:
        if scope["type"] != "http":
            await app(scope, receive, send)
            return

        # Extract request info from scope
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}

        # Log request details
        logger.info("=" * 60)
        logger.info(f"=== Incoming Request: {method} {path} ===")
        if query_string:
            logger.info(f"Query string: {query_string}")
        logger.info(f"Client: {scope.get('client')}")

        # Log all headers
        logger.info("Headers:")
        for name, value in headers.items():
            # Mask authorization header value for security
            if mask_auth and name.lower() == "authorization":
                logger.info(f"  {name}: Bearer ***")
            else:
                logger.info(f"  {name}: {value}")

        # Log specific headers that MCP cares about
        content_type = headers.get("content-type", "NOT SET")
        origin = headers.get("origin", "NOT SET")
        host = headers.get("host", "NOT SET")
        mcp_session = headers.get("mcp-session-id", "NOT SET")
        mcp_protocol = headers.get("mcp-protocol-version", "NOT SET")

        logger.info("Key MCP headers:")
        logger.info(f"  Content-Type: {content_type}")
        logger.info(f"  Origin: {origin}")
        logger.info(f"  Host: {host}")
        logger.info(f"  Mcp-Session-Id: {mcp_session}")
        logger.info(f"  Mcp-Protocol-Version: {mcp_protocol}")

        # Track response status
        response_status = [None]
        response_headers: list[dict[str, str]] = [{}]

        async def send_wrapper(message: dict[str, Any]) -> Any:
            if message["type"] == "http.response.start":
                response_status[0] = message.get("status")
                response_headers[0] = {
                    k.decode(): v.decode() for k, v in message.get("headers", [])
                }

                # Log response status
                logger.info(f"=== Response: {response_status[0]} for {method} {path} ===")

                # If it's a 400 error, log more details
                if response_status[0] == 400:
                    logger.error("!!! 400 Bad Request returned !!!")
                    logger.error(f"Response headers: {response_headers[0]}")

            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and response_status[0] == 400:
                    # Log the response body for 400 errors
                    body_text = body.decode("utf-8", errors="replace")
                    logger.error(f"400 Response body: {body_text}")

            await send(message)

        # Log body for POST requests by wrapping receive
        body_logged = [False]

        async def receive_with_logging() -> Any:
            message = await receive()
            if message["type"] == "http.request" and not body_logged[0]:
                body_logged[0] = True
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if body:
                    body_preview = body[:1000].decode("utf-8", errors="replace")
                    if len(body) > 1000 or more_body:
                        body_preview += "... (truncated/more coming)"
                    logger.info(f"Request body preview ({len(body)} bytes): {body_preview}")
            return message

        logger.info("=" * 60)

        if method == "POST":
            await app(scope, receive_with_logging, send_wrapper)
        else:
            await app(scope, receive, send_wrapper)

    return middleware
