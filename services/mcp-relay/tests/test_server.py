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

        messages, has_more = store.get("test")
        assert len(messages) == 1
        assert messages[0].id == msg.id
        assert has_more is False

    def test_channel_isolation(self) -> None:
        store = MessageStore()
        store.add("ch-a", "message A")
        store.add("ch-b", "message B")

        a_msgs, _ = store.get("ch-a")
        b_msgs, _ = store.get("ch-b")

        assert len(a_msgs) == 1
        assert a_msgs[0].content == "message A"
        assert len(b_msgs) == 1
        assert b_msgs[0].content == "message B"

    def test_read_nonexistent_channel(self) -> None:
        store = MessageStore()
        messages, has_more = store.get("nope")
        assert messages == []
        assert has_more is False

    def test_since_timestamp_filtering(self) -> None:
        store = MessageStore()
        msg1 = store.add("test", "first")
        msg2 = store.add("test", "second")

        # Filter since the first message's timestamp — should only get second
        filtered, _ = store.get("test", since=msg1.timestamp)
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

        messages, has_more = store.get("test", limit=3)
        assert len(messages) == 3
        # Should return the most recent 3 (no cursor preserves original behavior)
        assert messages[0].content == "msg-7"
        assert messages[2].content == "msg-9"
        assert has_more is True

    def test_limit_capped_at_max(self) -> None:
        store = MessageStore()
        store.add("test", "msg")

        # Requesting more than MAX_READ_LIMIT should be capped
        messages, has_more = store.get("test", limit=99999)
        assert len(messages) == 1  # only 1 message exists, but limit was capped
        assert has_more is False

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
        messages, _ = store.get("test")
        assert len(messages) == 2

        result = store.clear("test")
        assert result is True
        messages, _ = store.get("test")
        assert messages == []

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
        messages, _ = store.get("test")
        assert messages == []
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

        messages, _ = store.get("test")
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

    def test_sort_order_desc_default(self) -> None:
        """Default sort_order='desc' returns the newest N messages."""
        store = MessageStore()
        for i in range(5):
            store.add("test", f"msg-{i}")

        messages, _ = store.get("test", limit=3)
        assert len(messages) == 3
        assert messages[0].content == "msg-2"
        assert messages[1].content == "msg-3"
        assert messages[2].content == "msg-4"

    def test_sort_order_desc_explicit(self) -> None:
        """Explicit sort_order='desc' returns the newest N messages."""
        store = MessageStore()
        for i in range(5):
            store.add("test", f"msg-{i}")

        messages, _ = store.get("test", limit=3, sort_order="desc")
        assert len(messages) == 3
        assert messages[0].content == "msg-2"
        assert messages[2].content == "msg-4"

    def test_sort_order_asc_returns_oldest_first(self) -> None:
        """sort_order='asc' returns the oldest N messages."""
        store = MessageStore()
        for i in range(5):
            store.add("test", f"msg-{i}")

        messages, _ = store.get("test", limit=3, sort_order="asc")
        assert len(messages) == 3
        assert messages[0].content == "msg-0"
        assert messages[1].content == "msg-1"
        assert messages[2].content == "msg-2"

    def test_sort_order_asc_with_since(self) -> None:
        """sort_order='asc' combined with since filters correctly."""
        store = MessageStore()
        msg0 = store.add("test", "msg-0")
        store.add("test", "msg-1")
        store.add("test", "msg-2")
        store.add("test", "msg-3")

        messages, _ = store.get("test", since=msg0.timestamp, limit=2, sort_order="asc")
        assert len(messages) == 2
        assert messages[0].content == "msg-1"
        assert messages[1].content == "msg-2"

    def test_sort_order_desc_with_since(self) -> None:
        """sort_order='desc' combined with since returns newest of filtered messages."""
        store = MessageStore()
        msg0 = store.add("test", "msg-0")
        store.add("test", "msg-1")
        store.add("test", "msg-2")
        store.add("test", "msg-3")

        messages, _ = store.get("test", since=msg0.timestamp, limit=2, sort_order="desc")
        assert len(messages) == 2
        assert messages[0].content == "msg-2"
        assert messages[1].content == "msg-3"

    def test_sort_order_invalid_raises(self) -> None:
        """Invalid sort_order raises ValueError."""
        store = MessageStore()
        store.add("test", "msg")

        with pytest.raises(ValueError, match="Invalid sort_order"):
            store.get("test", sort_order="random")

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


class TestCursorPagination:
    """Tests for cursor-based pagination (after/before message ID)."""

    def _add_messages(self, store: MessageStore, channel: str, count: int) -> list[str]:
        """Add ``count`` messages and return their IDs in order."""
        ids = []
        for i in range(count):
            msg = store.add(channel, f"msg-{i}")
            ids.append(msg.id)
        return ids

    # ------------------------------------------------------------------ after

    def test_after_returns_messages_after_cursor(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 5)

        # after the 2nd message → should get msg-2, msg-3, msg-4
        messages, _ = store.get("test", after=ids[1])
        assert len(messages) == 3
        assert messages[0].content == "msg-2"
        assert messages[2].content == "msg-4"

    def test_after_last_message_returns_empty(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 3)

        messages, has_more = store.get("test", after=ids[-1])
        assert messages == []
        assert has_more is False

    def test_after_first_message_returns_rest(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 4)

        messages, _ = store.get("test", after=ids[0])
        assert len(messages) == 3
        assert messages[0].content == "msg-1"

    def test_after_invalid_id_raises(self) -> None:
        store = MessageStore()
        self._add_messages(store, "test", 3)

        with pytest.raises(ValueError, match="Cursor ID not found"):
            store.get("test", after="nonexistent-id")

    # ----------------------------------------------------------------- before

    def test_before_returns_messages_before_cursor(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 5)

        # before the 4th message (index 3) → should get msg-0, msg-1, msg-2
        messages, _ = store.get("test", before=ids[3])
        assert len(messages) == 3
        assert messages[0].content == "msg-0"
        assert messages[2].content == "msg-2"

    def test_before_first_message_returns_empty(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 3)

        messages, has_more = store.get("test", before=ids[0])
        assert messages == []
        assert has_more is False

    def test_before_last_message_returns_rest(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 4)

        messages, _ = store.get("test", before=ids[-1])
        assert len(messages) == 3
        assert messages[-1].content == "msg-2"

    def test_before_invalid_id_raises(self) -> None:
        store = MessageStore()
        self._add_messages(store, "test", 3)

        with pytest.raises(ValueError, match="Cursor ID not found"):
            store.get("test", before="nonexistent-id")

    # --------------------------------------------------------------- has_more

    def test_has_more_true_when_results_exceed_limit(self) -> None:
        store = MessageStore()
        self._add_messages(store, "test", 10)

        messages, has_more = store.get("test", limit=5)
        assert len(messages) == 5
        assert has_more is True

    def test_has_more_false_when_results_fit_in_limit(self) -> None:
        store = MessageStore()
        self._add_messages(store, "test", 3)

        messages, has_more = store.get("test", limit=10)
        assert len(messages) == 3
        assert has_more is False

    def test_has_more_false_when_exactly_limit(self) -> None:
        store = MessageStore()
        self._add_messages(store, "test", 5)

        messages, has_more = store.get("test", limit=5)
        assert len(messages) == 5
        assert has_more is False

    def test_has_more_with_after_cursor(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 10)

        # after first message → 9 remaining; with limit=5 → has_more=True
        messages, has_more = store.get("test", after=ids[0], limit=5)
        assert len(messages) == 5
        assert has_more is True

    def test_has_more_with_before_cursor(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 10)

        # before last message (msg-9) → 9 remaining (msg-0..msg-8); with limit=5 →
        # backward paging returns the most recent 5: msg-4, msg-5, msg-6, msg-7, msg-8
        messages, has_more = store.get("test", before=ids[-1], limit=5)
        assert len(messages) == 5
        assert has_more is True
        assert messages[0].content == "msg-4"
        assert messages[4].content == "msg-8"

    def test_before_returns_most_recent_within_limit(self) -> None:
        """before cursor with limit returns the most recent N messages before the cursor."""
        store = MessageStore()
        ids = self._add_messages(store, "test", 10)

        # 10 messages: msg-0..msg-9
        # before msg-9 → 9 messages [msg-0..msg-8]; limit=3 → msg-6, msg-7, msg-8
        messages, has_more = store.get("test", before=ids[9], limit=3)
        assert len(messages) == 3
        assert has_more is True
        assert messages[0].content == "msg-6"
        assert messages[1].content == "msg-7"
        assert messages[2].content == "msg-8"

    # ----------------------------------------------------- combined filters

    def test_after_combined_with_since(self) -> None:
        store = MessageStore()
        msg0 = store.add("test", "msg-0")
        store.add("test", "msg-1")
        msg2 = store.add("test", "msg-2")
        store.add("test", "msg-3")

        # since filters to msg-1, msg-2, msg-3; after=msg2.id → msg-3 only
        messages, _ = store.get("test", since=msg0.timestamp, after=msg2.id)
        assert len(messages) == 1
        assert messages[0].content == "msg-3"

    def test_after_combined_with_limit_has_more(self) -> None:
        store = MessageStore()
        ids = self._add_messages(store, "test", 20)

        # after the 5th → 15 remaining; limit=5 → has_more=True
        messages, has_more = store.get("test", after=ids[4], limit=5)
        assert len(messages) == 5
        assert has_more is True

    def test_sequential_pagination_forward(self) -> None:
        """Paginating forward with `after` covers all messages exactly once.

        Forward pagination starts from a known starting point (the first message ID)
        and uses `after=<id>` to advance through subsequent pages.
        """
        store = MessageStore()
        all_ids = self._add_messages(store, "test", 10)

        # Use the sentinel approach: start before the first message.
        # First page: messages after the first ID (ids[0])
        seen_contents: list[str] = []

        # Get the first page starting after msg-0
        cursor = all_ids[0]  # start after the first message
        seen_contents.append("msg-0")  # msg-0 is the starting cursor message

        while True:
            messages, has_more = store.get("test", after=cursor, limit=3)
            if not messages:
                break
            seen_contents.extend(m.content for m in messages)
            cursor = messages[-1].id
            if not has_more:
                break

        assert seen_contents == [f"msg-{i}" for i in range(10)]

    def test_sequential_pagination_all_ids_match(self) -> None:
        """IDs returned during `after` pagination match insertion order."""
        store = MessageStore()
        all_ids = self._add_messages(store, "test", 9)

        # Paginate starting after the very first message
        collected_ids: list[str] = [all_ids[0]]
        cursor = all_ids[0]

        while True:
            messages, has_more = store.get("test", after=cursor, limit=3)
            if not messages:
                break
            collected_ids.extend(m.id for m in messages)
            cursor = messages[-1].id
            if not has_more:
                break

        assert collected_ids == all_ids


class TestStoreIntegration:
    """Integration tests exercising the store the way tools would."""

    def test_send_read_roundtrip(self) -> None:
        store = MessageStore()
        msg = store.add("e2e", "test message", "sender-a")

        messages, _ = store.get("e2e")
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
        msgs, _ = store.get("ch1")
        assert msgs == []
        msgs2, _ = store.get("ch2")
        assert len(msgs2) == 1

    def test_limit_respected(self) -> None:
        store = MessageStore()
        for i in range(MAX_READ_LIMIT + 50):
            store.add("big", f"msg-{i}")

        messages, _ = store.get("big", limit=MAX_READ_LIMIT + 100)
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
