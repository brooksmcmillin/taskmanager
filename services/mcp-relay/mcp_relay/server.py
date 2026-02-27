"""MCP Relay Server — Inter-session message broker for dev workflows."""

import asyncio
import json
import logging
import os
import sys
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import click
from dotenv import load_dotenv
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp_resource_framework.auth import IntrospectionTokenVerifier
from mcp_resource_framework.middleware import NormalizePathMiddleware
from mcp_resource_framework.oauth_discovery import register_oauth_discovery_endpoints
from pydantic import AnyHttpUrl

logger = logging.getLogger(__name__)

load_dotenv()

MAX_MESSAGES_PER_CHANNEL = int(os.environ.get("MAX_MESSAGES_PER_CHANNEL", "1000"))
MAX_CHANNELS = int(os.environ.get("MAX_CHANNELS", "100"))
MAX_MESSAGE_SIZE = int(os.environ.get("MAX_MESSAGE_SIZE", "65536"))  # 64 KB
MAX_READ_LIMIT = 200

DEFAULT_SCOPE = ["read"]

# OAuth client credentials
MCP_AUTH_SERVER = os.environ.get("MCP_AUTH_SERVER", "http://localhost:9000")


@dataclass
class Message:
    id: str
    channel: str
    sender: str
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "channel": self.channel,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class ChannelInfo:
    name: str
    message_count: int
    last_activity: str | None


class MessageStore:
    """In-memory message store with per-channel deques."""

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

    def add(self, channel: str, content: str, sender: str = "anonymous") -> Message:
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

    def get(
        self,
        channel: str,
        since: str | None = None,
        limit: int = 50,
    ) -> list[Message]:
        if channel not in self._channels:
            return []

        limit = min(limit, MAX_READ_LIMIT)
        messages = list(self._channels[channel])

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                raise ValueError(f"Invalid ISO timestamp for 'since': {since}") from None
            messages = [m for m in messages if datetime.fromisoformat(m.timestamp) > since_dt]

        return messages[-limit:]

    def list_channels(self) -> list[ChannelInfo]:
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

    def clear(self, channel: str) -> bool:
        if channel in self._channels:
            self._channels[channel].clear()
            return True
        return False

    async def wait_for_new(
        self,
        channel: str,
        since: str | None = None,
        timeout: int = 30,
    ) -> tuple[list[Message], bool]:
        """Wait for new messages. Returns (messages, timed_out)."""
        # Check for existing messages first
        existing = self.get(channel, since=since)
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

        return self.get(channel, since=since), timed_out


# Global store instance
store = MessageStore()


def create_relay_server(
    server_url: str,
    auth_server_url: str,
    auth_server_public_url: str,
) -> FastMCP:
    """Create the MCP Relay Server with OAuth-protected message broker tools."""
    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=f"{auth_server_url}/introspect",
        server_url=server_url,
        validate_resource=False,
    )

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
        scopes=DEFAULT_SCOPE,
    )

    @app.tool()
    async def send_message(
        channel: str,
        content: str,
        sender: str = "anonymous",
    ) -> str:
        """Send a message to a named channel.

        Args:
            channel: Channel name (e.g. 'client-to-server', 'debug')
            content: Message content (max 64 KB)
            sender: Sender identifier (e.g. 'client-session', 'server-session')

        Returns:
            JSON with the sent message details
        """
        try:
            msg = store.add(channel, content, sender)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        logger.info(f"Message sent to #{channel} by {sender} ({len(content)} bytes)")
        return json.dumps(msg.to_dict())

    @app.tool()
    async def read_messages(
        channel: str,
        since: str | None = None,
        limit: int = 50,
    ) -> str:
        """Read messages from a channel.

        Args:
            channel: Channel name to read from
            since: ISO timestamp — only return messages after this time (optional)
            limit: Max messages to return (default 50, max 200)

        Returns:
            JSON with messages array and count
        """
        try:
            messages = store.get(channel, since=since, limit=limit)
        except ValueError as e:
            return json.dumps({"error": str(e)})
        return json.dumps(
            {
                "channel": channel,
                "messages": [m.to_dict() for m in messages],
                "count": len(messages),
            }
        )

    @app.tool()
    async def list_channels() -> str:
        """List all channels with message counts and last activity.

        Returns:
            JSON with channels array
        """
        channels = store.list_channels()
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
        cleared = store.clear(channel)
        return json.dumps(
            {
                "channel": channel,
                "cleared": cleared,
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
        mcp_server = create_relay_server(server_url, auth_server, auth_server_public_url)

        logger.info("=" * 60)
        logger.info(f"MCP Relay Server running on http://{host}:{port}")
        logger.info(f"MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"Auth server (internal): {auth_server}")
        logger.info(f"Auth server (public): {auth_server_public_url}")
        logger.info(f"Max messages/channel: {MAX_MESSAGES_PER_CHANNEL}")
        logger.info(f"Max channels: {MAX_CHANNELS}")
        logger.info("=" * 60)

        import uvicorn

        starlette_app = mcp_server.streamable_http_app()
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
