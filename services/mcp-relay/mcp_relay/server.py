"""MCP Relay Server — Inter-session message broker for dev workflows."""

import asyncio
import json
import logging
import os
import re
import sys
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.middleware import NormalizePathMiddleware
from mcp_resource_framework.oauth_discovery import register_oauth_discovery_endpoints
from pydantic import AnyHttpUrl

from mcp_relay.api import create_api_app
from mcp_relay.debug import create_debug_app
from mcp_relay.types import MAX_READ_LIMIT, ChannelInfo, Message

logger = logging.getLogger(__name__)

load_dotenv()

MAX_MESSAGES_PER_CHANNEL = int(os.environ.get("MAX_MESSAGES_PER_CHANNEL", "1000"))
MAX_CHANNELS = int(os.environ.get("MAX_CHANNELS", "100"))
MAX_MESSAGE_SIZE = int(os.environ.get("MAX_MESSAGE_SIZE", "65536"))  # 64 KB
MAX_CHANNEL_NAME_LENGTH = 64

# Allowlist: alphanumeric, hyphens, and underscores only.
# This prevents path traversal (e.g. '../../etc/passwd') and keeps
# the channel namespace clean for future file-backed storage.
# Use \Z (not $) to avoid matching trailing newlines.
_CHANNEL_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+\Z")

# Standard UUID format (any version): xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Used to validate message_id before logging, preventing log injection via
# embedded newlines or other control characters.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z",
    re.IGNORECASE,
)

DEFAULT_SCOPE = ["read"]
DELETE_SCOPE = "delete"
ALL_SCOPES = [*DEFAULT_SCOPE, DELETE_SCOPE]

# OAuth client credentials
MCP_AUTH_SERVER = os.environ.get("MCP_AUTH_SERVER", "http://localhost:9000")


def validate_channel_name(channel: str) -> None:
    """Validate that a channel name meets naming requirements.

    Channel names must consist solely of alphanumeric characters, hyphens, and
    underscores, and must be between 1 and MAX_CHANNEL_NAME_LENGTH characters long.
    This prevents path traversal attacks (e.g. '../../etc/passwd') and keeps the
    channel namespace clean for future file-backed storage implementations.

    Args:
        channel: The channel name to validate.

    Raises:
        ValueError: If the channel name is empty, too long, or contains
            disallowed characters.
    """
    if not channel:
        raise ValueError("Channel name must not be empty.")
    if len(channel) > MAX_CHANNEL_NAME_LENGTH:
        raise ValueError(
            f"Channel name too long: {len(channel)} chars (max {MAX_CHANNEL_NAME_LENGTH})."
        )
    if not _CHANNEL_NAME_RE.match(channel):
        raise ValueError(
            "Invalid channel name. "
            "Only alphanumeric characters, hyphens (-), and underscores (_) are allowed."
        )


def validate_message_id(message_id: str) -> None:
    """Validate that a message ID is a well-formed UUID.

    Message IDs are UUIDs assigned at send time. Validating the format before
    logging prevents log-injection attacks via a crafted message_id containing
    embedded newlines or other control characters.

    Args:
        message_id: The message ID string to validate.

    Raises:
        ValueError: If the message_id is not a valid UUID string.
    """
    if not _UUID_RE.match(message_id):
        raise ValueError("Invalid message ID format: must be a UUID.")


class MessageStore:
    """In-memory message store with per-channel deques.

    All public methods are async-compatible to allow swapping in alternative
    backends (e.g. RedisMessageStore) without changing callers.
    """

    def __init__(
        self,
        max_per_channel: int = MAX_MESSAGES_PER_CHANNEL,
        max_channels: int = MAX_CHANNELS,
        max_message_size: int = MAX_MESSAGE_SIZE,
    ) -> None:
        self._channels: dict[str, deque[Message]] = {}
        self._max_per_channel = max_per_channel
        self._max_channels = max_channels
        self._max_message_size = max_message_size
        self._events: dict[str, asyncio.Event] = {}

    async def add(self, channel: str, content: str, sender: str = "anonymous") -> Message:
        if len(content) > self._max_message_size:
            raise ValueError(
                f"Message too large: {len(content)} bytes (max {self._max_message_size})"
            )

        if channel not in self._channels:
            if len(self._channels) >= self._max_channels:
                raise ValueError(f"Channel limit reached: {self._max_channels} channels")
            self._channels[channel] = deque(maxlen=self._max_per_channel)
        if channel not in self._events:
            self._events[channel] = asyncio.Event()

        msg = Message(
            id=str(uuid.uuid4()),
            channel=channel,
            sender=sender,
            content=content,
            timestamp=datetime.now(UTC).isoformat(),
        )
        self._channels[channel].append(msg)

        # Signal waiters that a new message arrived
        if channel in self._events:
            self._events[channel].set()
            self._events[channel] = asyncio.Event()

        return msg

    async def get(
        self,
        channel: str,
        since: str | None = None,
        limit: int = 50,
        sort_order: str = "desc",
        after: str | None = None,
        before: str | None = None,
    ) -> tuple[list[Message], bool]:
        """Retrieve messages from a channel with optional filtering.

        Args:
            channel: Channel name to read from.
            since: ISO timestamp — only return messages after this time (optional).
            limit: Max messages to return (capped at MAX_READ_LIMIT).
            sort_order: ``'desc'`` returns the newest N messages (default);
                ``'asc'`` returns the oldest N. Ignored when ``after`` or
                ``before`` is provided.
            after: Message ID cursor — return messages strictly after this ID (optional).
                Enables forward pagination; ``sort_order`` is ignored.
            before: Message ID cursor — return messages strictly before this ID (optional).
                Enables backward pagination; ``sort_order`` is ignored.

        Returns:
            A tuple of (messages, has_more) where has_more indicates that additional
            messages exist beyond the returned page.

        Raises:
            ValueError: If ``since`` is not a valid ISO timestamp, if ``sort_order``
                is not ``'asc'`` or ``'desc'``, or if ``after``/``before`` reference
                an ID that does not exist in the channel.
        """
        if channel not in self._channels:
            return [], False

        if sort_order not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_order: '{sort_order}'. Must be 'asc' or 'desc'.")

        limit = min(limit, MAX_READ_LIMIT)
        messages = list(self._channels[channel])

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                raise ValueError(f"Invalid ISO timestamp for 'since': {since}") from None
            messages = [m for m in messages if datetime.fromisoformat(m.timestamp) > since_dt]

        if after:
            after_idx = next((i for i, m in enumerate(messages) if m.id == after), None)
            if after_idx is None:
                raise ValueError(f"Cursor ID not found: {after}")
            messages = messages[after_idx + 1 :]
            # Forward pagination: return the oldest N after the cursor
            has_more = len(messages) > limit
            return messages[:limit], has_more

        if before:
            before_idx = next((i for i, m in enumerate(messages) if m.id == before), None)
            if before_idx is None:
                raise ValueError(f"Cursor ID not found: {before}")
            messages = messages[:before_idx]
            # Backward pagination: return the most recent N before the cursor
            has_more = len(messages) > limit
            return messages[-limit:], has_more

        # No cursor: sort_order controls which N messages to return
        has_more = len(messages) > limit
        if sort_order == "asc":
            return messages[:limit], has_more
        return messages[-limit:], has_more

    async def list_channels(self) -> list[ChannelInfo]:
        result: list[ChannelInfo] = []
        for name, msgs in self._channels.items():
            last_activity = msgs[-1].timestamp if msgs else None
            result.append(
                ChannelInfo(
                    name=name,
                    message_count=len(msgs),
                    last_activity=last_activity,
                )
            )
        return result

    async def clear(self, channel: str) -> bool:
        if channel in self._channels:
            self._channels[channel].clear()
            return True
        return False

    async def delete(self, channel: str) -> bool:
        """Fully remove a channel and its event from the store.

        Unlike clear(), which empties the message queue but keeps the channel
        entry, delete() removes the channel entirely so it no longer appears
        in list_channels().

        Args:
            channel: The channel name to remove.

        Returns:
            True if the channel existed and was deleted, False otherwise.
        """
        if channel not in self._channels:
            return False
        del self._channels[channel]
        self._events.pop(channel, None)
        return True

    async def delete_message(
        self,
        channel: str,
        message_id: str,
        sender: str | None = None,
    ) -> bool:
        """Delete a single message by ID from a channel.

        Since deques don't support efficient random deletion, the deque is
        rebuilt without the target message.

        When `sender` is provided the message is only deleted if its stored
        sender matches, preventing one caller from deleting another caller's
        messages.

        Args:
            channel: The channel containing the message.
            message_id: The UUID string of the message to delete.
            sender: If given, only delete the message when its sender field
                matches this value exactly.

        Returns:
            True if the message was found (and, if sender was specified,
            matched) and deleted, False otherwise.
        """
        if channel not in self._channels:
            return False
        original = self._channels[channel]

        def _should_keep(m: Message) -> bool:
            if m.id != message_id:
                return True
            # Same ID — only remove if sender check passes
            return bool(sender is not None and m.sender != sender)

        new_deque: deque[Message] = deque(
            (m for m in original if _should_keep(m)),
            maxlen=original.maxlen,
        )
        if len(new_deque) == len(original):
            # No message was removed — ID not found or sender mismatch
            return False
        self._channels[channel] = new_deque
        return True

    async def wait_for_new(
        self,
        channel: str,
        since: str | None = None,
        timeout: int = 30,
    ) -> tuple[list[Message], bool]:
        """Wait for new messages. Returns (messages, timed_out)."""
        # Check for existing messages first
        existing, _ = await self.get(channel, since=since)
        if existing:
            return existing, False

        # Ensure event exists for this channel
        if channel not in self._events:
            self._events[channel] = asyncio.Event()

        event = self._events[channel]
        timed_out = False
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            timed_out = True
            return [], True

        messages, _ = await self.get(channel, since=since)
        return messages, timed_out


def create_store() -> MessageStore:
    """Create a message store based on environment configuration.

    Set ``RELAY_STORE_BACKEND=redis`` and ``REDIS_URL`` to use Redis.
    Defaults to in-memory storage.
    """
    backend = os.environ.get("RELAY_STORE_BACKEND", "redis").lower()
    if backend == "redis":
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            import redis.asyncio as aioredis
        except ImportError:
            logger.error(
                "RELAY_STORE_BACKEND=redis but 'redis' package is not installed. "
                "Install it with: uv add redis"
            )
            raise
        from mcp_relay.redis_store import RedisMessageStore

        client = aioredis.from_url(redis_url, decode_responses=False)
        safe_url = urlparse(redis_url)._replace(netloc=urlparse(redis_url).hostname + (f":{urlparse(redis_url).port}" if urlparse(redis_url).port else ""))
        logger.info(f"Using Redis message store: {safe_url.geturl()}")
        return RedisMessageStore(  # type: ignore[return-value]
            redis=client,
            max_per_channel=MAX_MESSAGES_PER_CHANNEL,
            max_channels=MAX_CHANNELS,
            max_message_size=MAX_MESSAGE_SIZE,
        )
    logger.info("Using in-memory message store")
    return MessageStore()


# Global store instance
store: MessageStore = create_store()


def create_token_verifier(
    server_url: str,
    auth_server_url: str,
) -> IntrospectionTokenVerifier:
    """Create an OAuth token introspection verifier."""
    return IntrospectionTokenVerifier(
        introspection_endpoint=f"{auth_server_url}/introspect",
        server_url=server_url,
        validate_resource=False,
    )


def create_relay_server(
    server_url: str,
    auth_server_url: str,
    auth_server_public_url: str,
    token_verifier: IntrospectionTokenVerifier | None = None,
) -> FastMCP:
    """Create the MCP Relay Server with OAuth-protected message broker tools."""
    if token_verifier is None:
        token_verifier = create_token_verifier(server_url, auth_server_url)

    parsed_url = urlparse(server_url)
    allowed_host = parsed_url.netloc

    app = FastMCP(
        name="MCP Relay",
        instructions=(
            "Message relay server for cross-session communication. "
            "Use send_message to post messages to named channels, "
            "and read_messages or wait_for_message to receive them."
        ),
        token_verifier=token_verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(auth_server_public_url),
            required_scopes=DEFAULT_SCOPE,
            resource_server_url=AnyHttpUrl(server_url),
        ),
        transport_security=TransportSecuritySettings(
            allowed_hosts=[allowed_host],
        ),
    )

    register_oauth_discovery_endpoints(
        app,
        server_url=server_url,
        auth_server_public_url=auth_server_public_url,
        scopes=ALL_SCOPES,
    )

    @app.tool()
    async def send_message(
        channel: str,
        content: str,
    ) -> str:
        """Send a message to a named channel.

        The sender is automatically set to the authenticated caller's OAuth
        client_id, ensuring consistent identity across send and delete
        operations.

        Args:
            channel: Channel name (e.g. 'client-to-server', 'debug')
            content: Message content (max 64 KB)

        Returns:
            JSON with the sent message details
        """
        token = get_access_token()
        if token is None:
            return json.dumps({"error": "Authentication required."})
        sender = token.client_id
        try:
            validate_channel_name(channel)
            msg = await store.add(channel, content, sender)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        logger.info(f"Message sent to #{channel} by {sender!r} ({len(content)} bytes)")
        return json.dumps(msg.to_dict())

    @app.tool()
    async def read_messages(
        channel: str,
        since: str | None = None,
        limit: int = 50,
        sort_order: str = "desc",
        after: str | None = None,
        before: str | None = None,
    ) -> str:
        """Read messages from a channel.

        Args:
            channel: Channel name to read from
            since: ISO timestamp — only return messages after this time (optional)
            limit: Max messages to return (default 50, max 200)
            sort_order: 'desc' returns the newest N messages (default), 'asc' returns
                the oldest N. Ignored when after or before cursor is provided.
            after: Message ID cursor — return messages strictly after this ID (optional).
                Use the last message ID from a previous response to page forward.
            before: Message ID cursor — return messages strictly before this ID (optional).
                Use the first message ID from a previous response to page backward.

        Returns:
            JSON with messages array, count, and has_more flag
        """
        try:
            validate_channel_name(channel)
            messages, has_more = await store.get(
                channel,
                since=since,
                limit=limit,
                sort_order=sort_order,
                after=after,
                before=before,
            )
        except ValueError as e:
            return json.dumps({"error": str(e)})
        return json.dumps(
            {
                "channel": channel,
                "messages": [m.to_dict() for m in messages],
                "count": len(messages),
                "has_more": has_more,
            }
        )

    @app.tool()
    async def list_channels() -> str:
        """List all channels with message counts and last activity.

        Returns:
            JSON with channels array
        """
        channels = await store.list_channels()
        return json.dumps(
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

    @app.tool()
    async def clear_channel(channel: str) -> str:
        """Delete all messages in a channel.

        Args:
            channel: Channel name to clear

        Returns:
            JSON with cleared status
        """
        try:
            validate_channel_name(channel)
            cleared = await store.clear(channel)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        return json.dumps(
            {
                "channel": channel,
                "cleared": cleared,
            }
        )

    @app.tool()
    async def delete_channel(channel: str) -> str:
        """Delete a channel and all its messages, removing it from the channel list.

        Unlike clear_channel (which empties messages but keeps the channel entry),
        delete_channel fully removes the channel so it no longer appears in
        list_channels. Use this to clean up stale channels.

        Requires the 'delete' OAuth scope in addition to the base 'read' scope.

        Args:
            channel: Channel name to delete

        Returns:
            JSON with deleted status
        """
        # Enforce delete scope at the tool level — this operation is irreversible
        # so it requires a higher-privilege scope than read-only tools.
        token = get_access_token()
        if token is None or DELETE_SCOPE not in token.scopes:
            return json.dumps(
                {
                    "error": "insufficient_scope",
                    "error_description": f"The '{DELETE_SCOPE}' scope is required to delete a channel.",
                }
            )
        try:
            validate_channel_name(channel)
            deleted = await store.delete(channel)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        return json.dumps(
            {
                "channel": channel,
                "deleted": deleted,
            }
        )

    @app.tool()
    async def delete_message(channel: str, message_id: str) -> str:
        """Delete a single message by ID from a channel.

        Use this to correct mistakes or remove sensitive content without
        clearing the entire channel. Only the authenticated caller who
        originally sent the message can delete it — the caller's OAuth
        client_id must match the message's sender field.

        Args:
            channel: Channel name containing the message
            message_id: UUID of the message to delete

        Returns:
            JSON with channel, message_id, and deleted status
        """
        try:
            validate_channel_name(channel)
            validate_message_id(message_id)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        # Use the verified OAuth client_id as the authoritative caller identity.
        # This prevents one client from deleting another client's messages.
        # Treat a missing token as an auth failure rather than a permission bypass.
        token = get_access_token()
        if token is None:
            return json.dumps({"error": "Authentication required."})
        caller_id = token.client_id

        deleted = await store.delete_message(channel, message_id, sender=caller_id)
        if deleted:
            logger.info(f"Message {message_id} deleted from #{channel} by {caller_id!r}")
        else:
            logger.debug(
                f"delete_message: no message removed "
                f"(channel={channel!r}, id={message_id!r}, caller={caller_id!r})"
            )
        return json.dumps(
            {
                "channel": channel,
                "message_id": message_id,
                "deleted": deleted,
            }
        )

    @app.tool()
    async def wait_for_message(
        channel: str,
        since: str | None = None,
        timeout: int = 30,
    ) -> str:
        """Long-poll: block until a new message arrives or timeout.

        Args:
            channel: Channel name to watch
            since: ISO timestamp — only return messages after this time (optional)
            timeout: Seconds to wait before returning empty (default 30, max 120)

        Returns:
            JSON with new messages (may be empty on timeout)
        """
        timeout = min(timeout, 120)
        try:
            validate_channel_name(channel)
            messages, timed_out = await store.wait_for_new(channel, since=since, timeout=timeout)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        return json.dumps(
            {
                "channel": channel,
                "messages": [m.to_dict() for m in messages],
                "count": len(messages),
                "timed_out": timed_out,
            }
        )

    return app


@click.command()
@click.option("--port", default=8002, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")  # noqa: S104
@click.option(
    "--auth-server",
    default=MCP_AUTH_SERVER,
    help="Authorization Server URL (internal, for introspection)",
)
@click.option(
    "--auth-server-public-url",
    help="Public Authorization Server URL (for OAuth metadata). Defaults to --auth-server value",
)
@click.option(
    "--server-url",
    help="External server URL (for OAuth). Defaults to http://localhost:PORT",
)
def main(
    port: int,
    host: str,
    auth_server: str,
    auth_server_public_url: str | None,
    server_url: str | None,
) -> None:
    """Run the MCP Relay Server."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        uv_logger.addHandler(handler)

    if not server_url:
        server_url = f"http://localhost:{port}"

    if not auth_server_public_url:
        auth_server_public_url = auth_server

    auth_server = auth_server.rstrip("/")
    auth_server_public_url = auth_server_public_url.rstrip("/")

    try:
        token_verifier = create_token_verifier(server_url, auth_server)
        mcp_server = create_relay_server(
            server_url, auth_server, auth_server_public_url, token_verifier=token_verifier
        )

        logger.info("=" * 60)
        logger.info(f"MCP Relay Server running on http://{host}:{port}")
        logger.info(f"MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"API endpoint: http://{host}:{port}/api/")
        logger.info(f"Auth server (internal): {auth_server}")
        logger.info(f"Auth server (public): {auth_server_public_url}")
        logger.info(f"Max messages/channel: {MAX_MESSAGES_PER_CHANNEL}")
        logger.info(f"Max channels: {MAX_CHANNELS}")
        logger.info("=" * 60)

        import uvicorn

        starlette_app = mcp_server.streamable_http_app()

        # Mount public OAuth-protected API
        api_app = create_api_app(store, token_verifier)
        starlette_app.mount("/api", api_app)

        debug_token = os.environ.get("MCP_RELAY_DEBUG_TOKEN", "").strip()
        debug_ui_enabled = os.environ.get("MCP_RELAY_DEBUG_UI", "").lower() in (
            "1",
            "true",
            "yes",
        )
        if debug_token:
            debug_app = create_debug_app(
                store, token=debug_token, include_ui=debug_ui_enabled
            )
            starlette_app.mount("/debug", debug_app)
            if debug_ui_enabled:
                logger.info(f"Debug UI + API: http://{host}:{port}/debug/ (token-protected)")
            else:
                logger.info(f"Debug API: http://{host}:{port}/debug/api/ (token-protected)")
        elif debug_ui_enabled:
            logger.error(
                "MCP_RELAY_DEBUG_UI=true but MCP_RELAY_DEBUG_TOKEN is not set. "
                "Refusing to start debug endpoints without authentication. "
                "Set MCP_RELAY_DEBUG_TOKEN to a secure token."
            )
            sys.exit(1)
        else:
            logger.info("Debug API disabled (set MCP_RELAY_DEBUG_TOKEN to enable)")

        app = NormalizePathMiddleware(starlette_app)

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
        )
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Exception details:")
        sys.exit(1)


if __name__ == "__main__":
    main()
