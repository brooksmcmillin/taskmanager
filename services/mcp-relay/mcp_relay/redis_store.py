"""Redis-backed message store for MCP Relay Server."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

from mcp_relay.types import MAX_READ_LIMIT, ChannelInfo, Message

logger = logging.getLogger(__name__)

# Redis key prefixes
_CHANNELS_KEY = "relay:channels"  # SET of channel names
_CHANNEL_PREFIX = "relay:channel:"  # LIST per channel (JSON messages)


class RedisMessageStore:
    """Redis-backed message store with the same async interface as MessageStore.

    Messages are stored as JSON in Redis lists (one list per channel).
    Channel names are tracked in a Redis set. New-message notifications
    use local asyncio events for the wait_for_new long-poll mechanism.
    """

    def __init__(
        self,
        redis: Redis,
        max_per_channel: int = 1000,
        max_channels: int = 100,
        max_message_size: int = 65536,
    ) -> None:
        self._redis = redis
        self._max_per_channel = max_per_channel
        self._max_channels = max_channels
        self._max_message_size = max_message_size
        self._events: dict[str, asyncio.Event] = {}

    def _channel_key(self, channel: str) -> str:
        return f"{_CHANNEL_PREFIX}{channel}"

    def _parse_message(self, raw: str | bytes) -> Message:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        d = json.loads(raw)
        return Message(
            id=d["id"],
            channel=d["channel"],
            sender=d["sender"],
            content=d["content"],
            timestamp=d["timestamp"],
        )

    async def _get_all_messages(self, channel: str) -> list[Message]:
        raw_messages = await self._redis.lrange(self._channel_key(channel), 0, -1)
        return [self._parse_message(raw) for raw in raw_messages]

    async def add(self, channel: str, content: str, sender: str = "anonymous") -> Message:
        """Add a message to a channel."""
        if len(content) > self._max_message_size:
            raise ValueError(
                f"Message too large: {len(content)} bytes (max {self._max_message_size})"
            )

        channel_key = self._channel_key(channel)
        is_new_channel = not await self._redis.sismember(_CHANNELS_KEY, channel)
        if is_new_channel:
            current_count = await self._redis.scard(_CHANNELS_KEY)
            if current_count >= self._max_channels:
                raise ValueError(f"Channel limit reached: {self._max_channels} channels")
            await self._redis.sadd(_CHANNELS_KEY, channel)

        msg = Message(
            id=str(uuid.uuid4()),
            channel=channel,
            sender=sender,
            content=content,
            timestamp=datetime.now(UTC).isoformat(),
        )

        await self._redis.rpush(channel_key, json.dumps(msg.to_dict()))
        await self._redis.ltrim(channel_key, -self._max_per_channel, -1)

        # Signal local asyncio waiters
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
        """Retrieve messages from a channel with optional filtering."""
        if sort_order not in ("asc", "desc"):
            raise ValueError(f"Invalid sort_order: '{sort_order}'. Must be 'asc' or 'desc'.")

        if not await self._redis.sismember(_CHANNELS_KEY, channel):
            return [], False

        limit = min(limit, MAX_READ_LIMIT)
        messages = await self._get_all_messages(channel)

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
            has_more = len(messages) > limit
            return messages[:limit], has_more

        if before:
            before_idx = next((i for i, m in enumerate(messages) if m.id == before), None)
            if before_idx is None:
                raise ValueError(f"Cursor ID not found: {before}")
            messages = messages[:before_idx]
            has_more = len(messages) > limit
            return messages[-limit:], has_more

        has_more = len(messages) > limit
        if sort_order == "asc":
            return messages[:limit], has_more
        return messages[-limit:], has_more

    async def list_channels(self) -> list[ChannelInfo]:
        """List all channels with message counts and last activity."""
        channel_names = await self._redis.smembers(_CHANNELS_KEY)
        result: list[ChannelInfo] = []
        for name in channel_names:
            if isinstance(name, bytes):
                name = name.decode("utf-8")
            channel_key = self._channel_key(name)
            count = await self._redis.llen(channel_key)
            last_activity: str | None = None
            if count > 0:
                raw_last = await self._redis.lindex(channel_key, -1)
                if raw_last:
                    last_msg = self._parse_message(raw_last)
                    last_activity = last_msg.timestamp
            result.append(ChannelInfo(name=name, message_count=count, last_activity=last_activity))
        return result

    async def clear(self, channel: str) -> bool:
        """Clear all messages in a channel."""
        if not await self._redis.sismember(_CHANNELS_KEY, channel):
            return False
        await self._redis.delete(self._channel_key(channel))
        return True

    async def delete(self, channel: str) -> bool:
        """Fully remove a channel and its messages."""
        if not await self._redis.sismember(_CHANNELS_KEY, channel):
            return False
        await self._redis.delete(self._channel_key(channel))
        await self._redis.srem(_CHANNELS_KEY, channel)
        self._events.pop(channel, None)
        return True

    async def delete_message(
        self,
        channel: str,
        message_id: str,
        sender: str | None = None,
    ) -> bool:
        """Delete a single message by ID from a channel."""
        if not await self._redis.sismember(_CHANNELS_KEY, channel):
            return False

        channel_key = self._channel_key(channel)
        messages = await self._get_all_messages(channel)

        target = next((m for m in messages if m.id == message_id), None)
        if target is None:
            return False

        if sender is not None and target.sender != sender:
            return False

        new_messages = [m for m in messages if m.id != message_id]

        pipe = self._redis.pipeline()
        pipe.delete(channel_key)
        for m in new_messages:
            pipe.rpush(channel_key, json.dumps(m.to_dict()))
        await pipe.execute()

        return True

    async def wait_for_new(
        self,
        channel: str,
        since: str | None = None,
        timeout: int = 30,
    ) -> tuple[list[Message], bool]:
        """Wait for new messages. Returns (messages, timed_out)."""
        existing, _ = await self.get(channel, since=since)
        if existing:
            return existing, False

        if channel not in self._events:
            self._events[channel] = asyncio.Event()

        event = self._events[channel]
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except TimeoutError:
            return [], True

        messages, _ = await self.get(channel, since=since)
        return messages, False

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._redis.aclose()
