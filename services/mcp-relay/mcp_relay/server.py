"""MCP Relay Server — Inter-session message broker for dev workflows."""

import asyncio
import logging
import os
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime

import click
from dotenv import load_dotenv
from mcp.server.fastmcp.server import FastMCP

logger = logging.getLogger(__name__)

load_dotenv()

MAX_MESSAGES_PER_CHANNEL = int(os.environ.get("MAX_MESSAGES_PER_CHANNEL", "1000"))


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

    def __init__(self, max_per_channel: int = MAX_MESSAGES_PER_CHANNEL) -> None:
        self._channels: dict[str, deque[Message]] = {}
        self._max_per_channel = max_per_channel
        self._events: dict[str, asyncio.Event] = {}

    def add(self, channel: str, content: str, sender: str = "anonymous") -> Message:
        if channel not in self._channels:
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

        messages = list(self._channels[channel])

        if since:
            since_dt = datetime.fromisoformat(since)
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
    ) -> list[Message]:
        # Check for existing messages first
        existing = self.get(channel, since=since)
        if existing:
            return existing

        # Ensure event exists for this channel
        if channel not in self._events:
            self._events[channel] = asyncio.Event()

        event = self._events[channel]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            return []

        return self.get(channel, since=since)


# Global store instance
store = MessageStore()


def create_relay_server() -> FastMCP:
    """Create the MCP Relay Server with message broker tools."""
    app = FastMCP(
        name="MCP Relay",
        instructions=(
            "Message relay server for cross-session communication. "
            "Use send_message to post messages to named channels, "
            "and read_messages or wait_for_message to receive them."
        ),
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
            content: Message content
            sender: Sender identifier (e.g. 'client-session', 'server-session')

        Returns:
            JSON with the sent message details
        """
        import json

        msg = store.add(channel, content, sender)
        logger.info(f"Message sent to #{channel} by {sender}: {content[:100]}")
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
            limit: Max messages to return (default 50)

        Returns:
            JSON with messages array and count
        """
        import json

        messages = store.get(channel, since=since, limit=limit)
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
        import json

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
        import json

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
        import json

        timeout = min(timeout, 120)
        messages = await store.wait_for_new(channel, since=since, timeout=timeout)
        return json.dumps(
            {
                "channel": channel,
                "messages": [m.to_dict() for m in messages],
                "count": len(messages),
                "timed_out": len(messages) == 0,
            }
        )

    return app


@click.command()
@click.option("--port", default=8002, help="Port to listen on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")  # noqa: S104
def main(port: int, host: str) -> int:
    """Run the MCP Relay Server."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)

    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.handlers = []
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format))
        uv_logger.addHandler(handler)

    try:
        mcp_server = create_relay_server()

        logger.info("=" * 60)
        logger.info(f"MCP Relay Server running on http://{host}:{port}")
        logger.info(f"MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"Max messages per channel: {MAX_MESSAGES_PER_CHANNEL}")
        logger.info("=" * 60)

        import uvicorn

        starlette_app = mcp_server.streamable_http_app()

        uvicorn.run(
            starlette_app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
        )
        return 0
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.exception("Exception details:")
        return 1


if __name__ == "__main__":
    main()
