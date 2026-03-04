"""Public REST API with OAuth 2.0 token introspection auth."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

if TYPE_CHECKING:
    from mcp_resource_framework.auth import IntrospectionTokenVerifier
    from starlette.types import ASGIApp

    from mcp_relay.server import MessageStore

logger = logging.getLogger(__name__)

MAX_SENDER_LENGTH = 128


class OAuthTokenMiddleware(BaseHTTPMiddleware):
    """Validate OAuth Bearer tokens via introspection."""

    def __init__(self, app: ASGIApp, token_verifier: IntrospectionTokenVerifier) -> None:
        super().__init__(app)
        self.token_verifier = token_verifier

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]  # noqa: ANN001
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return JSONResponse(
                {"error": "Missing or invalid Authorization header"},
                status_code=401,
            )

        token_str = auth[len("Bearer ") :]
        access_token = await self.token_verifier.verify_token(token_str)
        if access_token is None:
            return JSONResponse(
                {"error": "Invalid or expired token"},
                status_code=401,
            )

        request.state.access_token = access_token
        return await call_next(request)


async def channels_handler(request: Request) -> JSONResponse:
    """Return all channels with message counts."""
    store: MessageStore = request.app.state.store
    channels = store.list_channels()
    return JSONResponse(
        {
            "channels": [
                {
                    "name": c.name,
                    "message_count": c.message_count,
                    "last_activity": c.last_activity,
                }
                for c in channels
            ],
        }
    )


async def messages_handler(request: Request) -> JSONResponse:
    """Return messages for a specific channel."""
    from mcp_relay.server import validate_channel_name

    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]
    since = request.query_params.get("since")
    limit_str = request.query_params.get("limit", "100")

    try:
        validate_channel_name(channel)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        limit = int(limit_str)
    except ValueError:
        return JSONResponse({"error": "Invalid limit parameter"}, status_code=400)

    if limit <= 0:
        limit = 100

    try:
        messages, _ = store.get(channel, since=since, limit=limit)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse(
        {
            "channel": channel,
            "messages": [m.to_dict() for m in messages],
            "count": len(messages),
        }
    )


async def send_handler(request: Request) -> JSONResponse:
    """Send a message to a channel. Sender is derived from OAuth client_id."""
    from mcp_relay.server import validate_channel_name

    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]

    try:
        validate_channel_name(channel)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    content = body.get("content", "")
    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    sender = request.state.access_token.client_id[:MAX_SENDER_LENGTH]

    try:
        msg = store.add(channel, content, sender)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    logger.info(f"API: Message sent to #{channel!r} by {sender!r} ({len(content)} bytes)")
    return JSONResponse(msg.to_dict(), status_code=201)


async def clear_handler(request: Request) -> JSONResponse:
    """Clear all messages in a channel. Requires the 'delete' scope."""
    from mcp_relay.server import DELETE_SCOPE, validate_channel_name

    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]

    try:
        validate_channel_name(channel)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    access_token = request.state.access_token
    if DELETE_SCOPE not in access_token.scopes:
        return JSONResponse(
            {
                "error": "insufficient_scope",
                "error_description": (
                    f"The '{DELETE_SCOPE}' scope is required to clear a channel."
                ),
            },
            status_code=403,
        )

    cleared = store.clear(channel)
    return JSONResponse({"channel": channel, "cleared": cleared})


def create_api_app(
    store: MessageStore,
    token_verifier: IntrospectionTokenVerifier,
) -> Starlette:
    """Create the public API Starlette sub-application with OAuth auth.

    Args:
        store: The MessageStore instance to expose.
        token_verifier: OAuth token introspection verifier.
    """
    app = Starlette(
        routes=[
            Route("/channels", channels_handler, methods=["GET"]),
            Route("/channels/{channel}/messages", messages_handler, methods=["GET"]),
            Route("/channels/{channel}/messages", send_handler, methods=["POST"]),
            Route("/channels/{channel}/clear", clear_handler, methods=["POST"]),
        ],
        middleware=[
            Middleware(OAuthTokenMiddleware, token_verifier=token_verifier),
        ],
    )
    app.state.store = store
    return app
