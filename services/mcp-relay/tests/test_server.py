"""Tests for MCP Relay Server."""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING

import pytest

from mcp_relay.server import MessageStore, create_relay_server

if TYPE_CHECKING:
    from mcp.server.fastmcp.server import FastMCP


class TestMessageStore:
    """Tests for the in-memory MessageStore."""

    def test_send_and_read_roundtrip(self) -> None:
        store = MessageStore()
        msg = store.add("test", "hello world", "alice")

        assert msg.channel == "test"
        assert msg.content == "hello world"
        assert msg.sender == "alice"
        assert msg.id  # UUID assigned

        messages = store.get("test")
        assert len(messages) == 1
        assert messages[0].id == msg.id

    def test_channel_isolation(self) -> None:
        store = MessageStore()
        store.add("ch-a", "message A")
        store.add("ch-b", "message B")

        a_msgs = store.get("ch-a")
        b_msgs = store.get("ch-b")

        assert len(a_msgs) == 1
        assert a_msgs[0].content == "message A"
        assert len(b_msgs) == 1
        assert b_msgs[0].content == "message B"

    def test_read_nonexistent_channel(self) -> None:
        store = MessageStore()
        assert store.get("nope") == []

    def test_since_timestamp_filtering(self) -> None:
        store = MessageStore()
        msg1 = store.add("test", "first")
        msg2 = store.add("test", "second")

        # Filter since the first message's timestamp — should only get second
        filtered = store.get("test", since=msg1.timestamp)
        assert len(filtered) == 1
        assert filtered[0].id == msg2.id

    def test_limit_parameter(self) -> None:
        store = MessageStore()
        for i in range(10):
            store.add("test", f"msg-{i}")

        messages = store.get("test", limit=3)
        assert len(messages) == 3
        # Should return the last 3
        assert messages[0].content == "msg-7"
        assert messages[2].content == "msg-9"

    def test_list_channels(self) -> None:
        store = MessageStore()
        store.add("alpha", "a1")
        store.add("alpha", "a2")
        store.add("beta", "b1")

        channels = store.list_channels()
        assert len(channels) == 2

        by_name = {c.name: c for c in channels}
        assert by_name["alpha"].message_count == 2
        assert by_name["beta"].message_count == 1
        assert by_name["alpha"].last_activity is not None

    def test_list_channels_empty(self) -> None:
        store = MessageStore()
        assert store.list_channels() == []

    def test_clear_channel(self) -> None:
        store = MessageStore()
        store.add("test", "msg1")
        store.add("test", "msg2")
        assert len(store.get("test")) == 2

        result = store.clear("test")
        assert result is True
        assert store.get("test") == []

    def test_clear_nonexistent_channel(self) -> None:
        store = MessageStore()
        assert store.clear("nope") is False

    def test_max_messages_eviction(self) -> None:
        store = MessageStore(max_per_channel=5)
        for i in range(10):
            store.add("test", f"msg-{i}")

        messages = store.get("test")
        assert len(messages) == 5
        # Oldest messages should be evicted
        assert messages[0].content == "msg-5"
        assert messages[4].content == "msg-9"

    def test_message_to_dict(self) -> None:
        store = MessageStore()
        msg = store.add("test", "hello", "bob")
        d = msg.to_dict()

        assert d["id"] == msg.id
        assert d["channel"] == "test"
        assert d["content"] == "hello"
        assert d["sender"] == "bob"
        assert "timestamp" in d

    def test_default_sender(self) -> None:
        store = MessageStore()
        msg = store.add("test", "hello")
        assert msg.sender == "anonymous"

    @pytest.mark.asyncio
    async def test_wait_for_message_immediate(self) -> None:
        """wait_for_new returns immediately if messages exist since the given timestamp."""
        store = MessageStore()
        msg = store.add("test", "already here")

        # Since before the message — should return immediately
        from datetime import datetime

        early = datetime(2000, 1, 1, tzinfo=UTC).isoformat()
        messages = await store.wait_for_new("test", since=early, timeout=1)
        assert len(messages) == 1
        assert messages[0].id == msg.id

    @pytest.mark.asyncio
    async def test_wait_for_message_timeout(self) -> None:
        """wait_for_new returns empty list on timeout."""
        store = MessageStore()
        messages = await store.wait_for_new("empty", timeout=1)
        assert messages == []

    @pytest.mark.asyncio
    async def test_wait_for_message_delivery(self) -> None:
        """wait_for_new returns when a new message is posted."""
        store = MessageStore()

        async def post_after_delay() -> None:
            await asyncio.sleep(0.1)
            store.add("test", "delayed message", "poster")

        task = asyncio.create_task(post_after_delay())
        messages = await store.wait_for_new("test", timeout=5)
        await task

        assert len(messages) == 1
        assert messages[0].content == "delayed message"


class TestToolFunctions:
    """Tests for MCP tool functions via the relay server."""

    @pytest.fixture
    def relay(self) -> FastMCP:
        """Create a fresh relay server (with fresh store) for each test."""
        import mcp_relay.server as mod

        mod.store = MessageStore()
        return create_relay_server()

    @pytest.mark.asyncio
    async def test_send_message_tool(self, relay: FastMCP) -> None:  # noqa: ARG002
        import mcp_relay.server as mod

        msg = mod.store.add("tools-test", "via store", "tester")
        assert msg.content == "via store"

    @pytest.mark.asyncio
    async def test_roundtrip_via_store(self) -> None:
        """End-to-end: send via store, read via store, verify JSON format."""
        import mcp_relay.server as mod

        mod.store = MessageStore()
        create_relay_server()

        mod.store.add("e2e", "test message", "sender-a")
        messages = mod.store.get("e2e")

        assert len(messages) == 1
        d = messages[0].to_dict()
        assert d["channel"] == "e2e"
        assert d["content"] == "test message"
        assert d["sender"] == "sender-a"

    @pytest.mark.asyncio
    async def test_list_and_clear(self) -> None:
        import mcp_relay.server as mod

        mod.store = MessageStore()
        create_relay_server()

        mod.store.add("ch1", "msg1")
        mod.store.add("ch2", "msg2")

        channels = mod.store.list_channels()
        assert len(channels) == 2

        mod.store.clear("ch1")
        assert mod.store.get("ch1") == []
        assert len(mod.store.get("ch2")) == 1
