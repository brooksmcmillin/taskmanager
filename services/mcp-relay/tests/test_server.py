"""Tests for MCP Relay Server."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from mcp_relay.server import (
    MAX_CHANNEL_NAME_LENGTH,
    MAX_READ_LIMIT,
    MessageStore,
    validate_channel_name,
)


class TestValidateChannelName:
    """Tests for the validate_channel_name helper."""

    def test_valid_names(self) -> None:
        valid = [
            "test",
            "my-channel",
            "my_channel",
            "Channel123",
            "a",
            "A-b_C-1",
            "a" * MAX_CHANNEL_NAME_LENGTH,  # exactly max length
        ]
        for name in valid:
            validate_channel_name(name)  # must not raise

    def test_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            validate_channel_name("")

    def test_rejects_path_traversal(self) -> None:
        with pytest.raises(ValueError, match="Invalid channel name"):
            validate_channel_name("../../etc/passwd")

    def test_rejects_dot_segments(self) -> None:
        with pytest.raises(ValueError, match="Invalid channel name"):
            validate_channel_name("../secret")

    def test_rejects_slash(self) -> None:
        with pytest.raises(ValueError, match="Invalid channel name"):
            validate_channel_name("a/b")

    def test_rejects_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid channel name"):
            validate_channel_name("my channel")

    def test_rejects_special_chars(self) -> None:
        for bad in ["@channel", "chan!el", "ch#1", "ch*", "ch&name", "ch=a", "ch.a"]:
            with pytest.raises(ValueError, match="Invalid channel name"):
                validate_channel_name(bad)

    def test_rejects_name_too_long(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            validate_channel_name("a" * (MAX_CHANNEL_NAME_LENGTH + 1))


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

    def test_since_invalid_timestamp(self) -> None:
        store = MessageStore()
        store.add("test", "msg")

        with pytest.raises(ValueError, match="Invalid ISO timestamp"):
            store.get("test", since="not-a-date")

    def test_limit_parameter(self) -> None:
        store = MessageStore()
        for i in range(10):
            store.add("test", f"msg-{i}")

        messages = store.get("test", limit=3)
        assert len(messages) == 3
        # Should return the last 3
        assert messages[0].content == "msg-7"
        assert messages[2].content == "msg-9"

    def test_limit_capped_at_max(self) -> None:
        store = MessageStore()
        store.add("test", "msg")

        # Requesting more than MAX_READ_LIMIT should be capped
        messages = store.get("test", limit=99999)
        assert len(messages) == 1  # only 1 message exists, but limit was capped

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

    def test_clear_channel_persists_in_list(self) -> None:
        """Clearing a channel keeps it in list_channels with message_count=0."""
        store = MessageStore()
        store.add("test", "msg1")
        store.clear("test")

        channels = store.list_channels()
        assert len(channels) == 1
        assert channels[0].name == "test"
        assert channels[0].message_count == 0

    def test_delete_channel_removes_from_store(self) -> None:
        store = MessageStore()
        store.add("test", "msg1")
        store.add("test", "msg2")

        result = store.delete("test")
        assert result is True
        assert store.get("test") == []
        assert store.list_channels() == []

    def test_delete_channel_nonexistent(self) -> None:
        store = MessageStore()
        assert store.delete("nope") is False

    def test_delete_channel_removes_from_list(self) -> None:
        """delete() removes the channel from list_channels entirely."""
        store = MessageStore()
        store.add("alpha", "a1")
        store.add("beta", "b1")

        store.delete("alpha")

        channels = store.list_channels()
        assert len(channels) == 1
        assert channels[0].name == "beta"

    def test_delete_channel_frees_slot_for_new_channel(self) -> None:
        """After deleting a channel, its slot can be reused within max_channels."""
        store = MessageStore(max_channels=2)
        store.add("ch1", "msg")
        store.add("ch2", "msg")

        # At capacity — adding a third channel should fail
        with pytest.raises(ValueError, match="Channel limit reached"):
            store.add("ch3", "msg")

        # Delete one and the slot becomes available
        store.delete("ch1")
        store.add("ch3", "msg")  # should not raise

        channels = {c.name for c in store.list_channels()}
        assert channels == {"ch2", "ch3"}

    def test_delete_cleared_channel_removes_it(self) -> None:
        """A channel that was cleared (message_count=0) can still be deleted."""
        store = MessageStore()
        store.add("test", "msg")
        store.clear("test")

        # Channel still visible after clear
        assert len(store.list_channels()) == 1

        result = store.delete("test")
        assert result is True
        assert store.list_channels() == []

    def test_delete_channel_removes_event(self) -> None:
        """delete() removes the asyncio event so the channel is fully gone."""
        store = MessageStore()
        store.add("test", "msg")

        assert "test" in store._events

        store.delete("test")

        assert "test" not in store._channels
        assert "test" not in store._events

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

    def test_max_channels_enforced(self) -> None:
        store = MessageStore(max_channels=3)
        store.add("ch1", "msg")
        store.add("ch2", "msg")
        store.add("ch3", "msg")

        with pytest.raises(ValueError, match="Channel limit reached"):
            store.add("ch4", "msg")

    def test_max_message_size_enforced(self) -> None:
        store = MessageStore(max_message_size=10)
        store.add("test", "short")  # OK

        with pytest.raises(ValueError, match="Message too large"):
            store.add("test", "x" * 11)

    @pytest.mark.asyncio
    async def test_wait_for_message_immediate(self) -> None:
        """wait_for_new returns immediately if messages exist since the given timestamp."""
        store = MessageStore()
        msg = store.add("test", "already here")

        early = datetime(2000, 1, 1, tzinfo=UTC).isoformat()
        messages, timed_out = await store.wait_for_new("test", since=early, timeout=1)
        assert len(messages) == 1
        assert messages[0].id == msg.id
        assert timed_out is False

    @pytest.mark.asyncio
    async def test_wait_for_message_timeout(self) -> None:
        """wait_for_new returns empty list on timeout."""
        store = MessageStore()
        messages, timed_out = await store.wait_for_new("empty", timeout=1)
        assert messages == []
        assert timed_out is True

    @pytest.mark.asyncio
    async def test_wait_for_message_delivery(self) -> None:
        """wait_for_new returns when a new message is posted."""
        store = MessageStore()

        async def post_after_delay() -> None:
            await asyncio.sleep(0.1)
            store.add("test", "delayed message", "poster")

        task = asyncio.create_task(post_after_delay())
        messages, timed_out = await store.wait_for_new("test", timeout=5)
        await task

        assert len(messages) == 1
        assert messages[0].content == "delayed message"
        assert timed_out is False


class TestStoreIntegration:
    """Integration tests exercising the store the way tools would."""

    def test_send_read_roundtrip(self) -> None:
        store = MessageStore()
        msg = store.add("e2e", "test message", "sender-a")

        messages = store.get("e2e")
        assert len(messages) == 1
        d = messages[0].to_dict()
        assert d["channel"] == "e2e"
        assert d["content"] == "test message"
        assert d["sender"] == "sender-a"
        assert d["id"] == msg.id

    def test_list_and_clear(self) -> None:
        store = MessageStore()
        store.add("ch1", "msg1")
        store.add("ch2", "msg2")

        channels = store.list_channels()
        assert len(channels) == 2

        store.clear("ch1")
        assert store.get("ch1") == []
        assert len(store.get("ch2")) == 1

    def test_limit_respected(self) -> None:
        store = MessageStore()
        for i in range(MAX_READ_LIMIT + 50):
            store.add("big", f"msg-{i}")

        messages = store.get("big", limit=MAX_READ_LIMIT + 100)
        assert len(messages) == MAX_READ_LIMIT

    def test_delete_channel_integration(self) -> None:
        """delete_channel fully removes a channel; clear_channel keeps the entry."""
        store = MessageStore()
        store.add("keep", "msg1")
        store.add("remove", "msg2")

        channels = store.list_channels()
        assert len(channels) == 2

        # clear_channel keeps the channel in the listing
        store.clear("keep")
        channels = store.list_channels()
        assert len(channels) == 2
        by_name = {c.name: c for c in channels}
        assert by_name["keep"].message_count == 0

        # delete_channel removes it entirely
        store.delete("remove")
        channels = store.list_channels()
        assert len(channels) == 1
        assert channels[0].name == "keep"
