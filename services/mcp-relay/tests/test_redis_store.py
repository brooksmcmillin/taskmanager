"""Tests for the Redis-backed message store.

These tests use fakeredis to avoid requiring a real Redis server.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

try:
    import fakeredis.aioredis

    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False

pytestmark = pytest.mark.skipif(not HAS_FAKEREDIS, reason="fakeredis not installed")


@pytest.fixture
async def redis():
    """Create a fake async Redis client."""
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest.fixture
async def store(redis):
    """Create a RedisMessageStore backed by fakeredis."""
    from mcp_relay.redis_store import RedisMessageStore

    return RedisMessageStore(redis=redis, max_per_channel=1000, max_channels=100)


class TestRedisMessageStore:
    """Tests for the Redis-backed MessageStore — mirrors TestMessageStore."""

    @pytest.mark.asyncio
    async def test_send_and_read_roundtrip(self, store) -> None:
        msg = await store.add("test", "hello world", "alice")

        assert msg.channel == "test"
        assert msg.content == "hello world"
        assert msg.sender == "alice"
        assert msg.id

        messages, has_more = await store.get("test")
        assert len(messages) == 1
        assert messages[0].id == msg.id
        assert has_more is False

    @pytest.mark.asyncio
    async def test_channel_isolation(self, store) -> None:
        await store.add("ch-a", "message A")
        await store.add("ch-b", "message B")

        a_msgs, _ = await store.get("ch-a")
        b_msgs, _ = await store.get("ch-b")

        assert len(a_msgs) == 1
        assert a_msgs[0].content == "message A"
        assert len(b_msgs) == 1
        assert b_msgs[0].content == "message B"

    @pytest.mark.asyncio
    async def test_read_nonexistent_channel(self, store) -> None:
        messages, has_more = await store.get("nope")
        assert messages == []
        assert has_more is False

    @pytest.mark.asyncio
    async def test_since_timestamp_filtering(self, store) -> None:
        msg1 = await store.add("test", "first")
        msg2 = await store.add("test", "second")

        filtered, _ = await store.get("test", since=msg1.timestamp)
        assert len(filtered) == 1
        assert filtered[0].id == msg2.id

    @pytest.mark.asyncio
    async def test_since_invalid_timestamp(self, store) -> None:
        await store.add("test", "msg")
        with pytest.raises(ValueError, match="Invalid ISO timestamp"):
            await store.get("test", since="not-a-date")

    @pytest.mark.asyncio
    async def test_limit_parameter(self, store) -> None:
        for i in range(10):
            await store.add("test", f"msg-{i}")

        messages, has_more = await store.get("test", limit=3)
        assert len(messages) == 3
        assert messages[0].content == "msg-7"
        assert messages[2].content == "msg-9"
        assert has_more is True

    @pytest.mark.asyncio
    async def test_list_channels(self, store) -> None:
        await store.add("alpha", "a1")
        await store.add("alpha", "a2")
        await store.add("beta", "b1")

        channels = await store.list_channels()
        assert len(channels) == 2

        by_name = {c.name: c for c in channels}
        assert by_name["alpha"].message_count == 2
        assert by_name["beta"].message_count == 1
        assert by_name["alpha"].last_activity is not None

    @pytest.mark.asyncio
    async def test_list_channels_empty(self, store) -> None:
        assert await store.list_channels() == []

    @pytest.mark.asyncio
    async def test_clear_channel(self, store) -> None:
        await store.add("test", "msg1")
        await store.add("test", "msg2")
        messages, _ = await store.get("test")
        assert len(messages) == 2

        result = await store.clear("test")
        assert result is True
        messages, _ = await store.get("test")
        assert messages == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent_channel(self, store) -> None:
        assert await store.clear("nope") is False

    @pytest.mark.asyncio
    async def test_delete_channel(self, store) -> None:
        await store.add("test", "msg1")
        result = await store.delete("test")
        assert result is True
        messages, _ = await store.get("test")
        assert messages == []
        assert await store.list_channels() == []

    @pytest.mark.asyncio
    async def test_delete_channel_nonexistent(self, store) -> None:
        assert await store.delete("nope") is False

    @pytest.mark.asyncio
    async def test_delete_message(self, store) -> None:
        msg1 = await store.add("test", "first", "alice")
        msg2 = await store.add("test", "second", "alice")
        msg3 = await store.add("test", "third", "alice")

        result = await store.delete_message("test", msg2.id)
        assert result is True

        remaining, _ = await store.get("test")
        assert len(remaining) == 2
        ids = [m.id for m in remaining]
        assert msg1.id in ids
        assert msg2.id not in ids
        assert msg3.id in ids

    @pytest.mark.asyncio
    async def test_delete_message_sender_match(self, store) -> None:
        msg = await store.add("test", "content", "alice")
        result = await store.delete_message("test", msg.id, sender="alice")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_message_sender_mismatch(self, store) -> None:
        msg = await store.add("test", "content", "alice")
        result = await store.delete_message("test", msg.id, sender="bob")
        assert result is False

    @pytest.mark.asyncio
    async def test_max_message_size(self, redis) -> None:
        from mcp_relay.redis_store import RedisMessageStore

        store = RedisMessageStore(redis=redis, max_message_size=10)
        await store.add("test", "short")
        with pytest.raises(ValueError, match="Message too large"):
            await store.add("test", "x" * 11)

    @pytest.mark.asyncio
    async def test_max_channels_enforced(self, redis) -> None:
        from mcp_relay.redis_store import RedisMessageStore

        store = RedisMessageStore(redis=redis, max_channels=2)
        await store.add("ch1", "msg")
        await store.add("ch2", "msg")
        with pytest.raises(ValueError, match="Channel limit reached"):
            await store.add("ch3", "msg")

    @pytest.mark.asyncio
    async def test_sort_order_asc(self, store) -> None:
        for i in range(5):
            await store.add("test", f"msg-{i}")

        messages, _ = await store.get("test", limit=3, sort_order="asc")
        assert len(messages) == 3
        assert messages[0].content == "msg-0"
        assert messages[2].content == "msg-2"

    @pytest.mark.asyncio
    async def test_sort_order_invalid(self, store) -> None:
        await store.add("test", "msg")
        with pytest.raises(ValueError, match="Invalid sort_order"):
            await store.get("test", sort_order="random")

    @pytest.mark.asyncio
    async def test_cursor_after(self, store) -> None:
        ids = []
        for i in range(5):
            msg = await store.add("test", f"msg-{i}")
            ids.append(msg.id)

        messages, _ = await store.get("test", after=ids[1])
        assert len(messages) == 3
        assert messages[0].content == "msg-2"

    @pytest.mark.asyncio
    async def test_cursor_before(self, store) -> None:
        ids = []
        for i in range(5):
            msg = await store.add("test", f"msg-{i}")
            ids.append(msg.id)

        messages, _ = await store.get("test", before=ids[3])
        assert len(messages) == 3
        assert messages[0].content == "msg-0"

    @pytest.mark.asyncio
    async def test_wait_for_new_immediate(self, store) -> None:
        msg = await store.add("test", "already here")
        early = datetime(2000, 1, 1, tzinfo=UTC).isoformat()
        messages, timed_out = await store.wait_for_new("test", since=early, timeout=1)
        assert len(messages) == 1
        assert messages[0].id == msg.id
        assert timed_out is False

    @pytest.mark.asyncio
    async def test_wait_for_new_timeout(self, store) -> None:
        messages, timed_out = await store.wait_for_new("empty", timeout=1)
        assert messages == []
        assert timed_out is True

    @pytest.mark.asyncio
    async def test_wait_for_new_delivery(self, store) -> None:
        async def post_after_delay():
            await asyncio.sleep(0.1)
            await store.add("test", "delayed message", "poster")

        task = asyncio.create_task(post_after_delay())
        messages, timed_out = await store.wait_for_new("test", timeout=5)
        await task

        assert len(messages) == 1
        assert messages[0].content == "delayed message"
        assert timed_out is False

    @pytest.mark.asyncio
    async def test_max_messages_eviction(self, redis) -> None:
        from mcp_relay.redis_store import RedisMessageStore

        store = RedisMessageStore(redis=redis, max_per_channel=5)
        for i in range(10):
            await store.add("test", f"msg-{i}")

        messages, _ = await store.get("test")
        assert len(messages) == 5
        assert messages[0].content == "msg-5"
        assert messages[4].content == "msg-9"
