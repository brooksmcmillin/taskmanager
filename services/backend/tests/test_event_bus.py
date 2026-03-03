"""Tests for the real-time event bus and SSE endpoint."""

import asyncio
import json

import pytest

from app.services.event_bus import Event, EventBus

# ---------------------------------------------------------------------------
# Unit tests for EventBus dispatch (no DB needed)
# ---------------------------------------------------------------------------


class TestEventBusDispatch:
    """Test EventBus._on_notify dispatch logic."""

    def setup_method(self) -> None:
        self.bus = EventBus()

    def _make_payload(
        self,
        *,
        table: str = "todos",
        op: str = "I",
        row_id: int = 1,
        user_id: int = 10,
        tab: str = "abc123",
    ) -> str:
        return json.dumps({
            "t": table, "op": op, "id": row_id,
            "uid": user_id, "tab": tab,
        })

    def test_dispatch_to_correct_user(self) -> None:
        q = self.bus.subscribe(10)
        self.bus._on_notify(None, 0, "events", self._make_payload(user_id=10))  # type: ignore[arg-type]
        assert not q.empty()
        event = q.get_nowait()
        assert isinstance(event, Event)
        assert event.table == "todos"
        assert event.op == "I"
        assert event.id == 1
        assert event.user_id == 10
        assert event.tab_id == "abc123"

    def test_events_for_user_a_dont_reach_user_b(self) -> None:
        q_a = self.bus.subscribe(10)
        q_b = self.bus.subscribe(20)
        self.bus._on_notify(None, 0, "events", self._make_payload(user_id=10))  # type: ignore[arg-type]
        assert not q_a.empty()
        assert q_b.empty()

    def test_malformed_payload_silently_dropped(self) -> None:
        q = self.bus.subscribe(10)
        # Invalid JSON
        self.bus._on_notify(None, 0, "events", "not-json")  # type: ignore[arg-type]
        assert q.empty()
        # Valid JSON but missing keys
        self.bus._on_notify(None, 0, "events", '{"foo": "bar"}')  # type: ignore[arg-type]
        assert q.empty()

    def test_full_queue_drops_event(self) -> None:
        """Full queues drop events without crashing."""
        q = self.bus.subscribe(10)
        # Fill the queue (maxsize=256)
        for i in range(256):
            self.bus._on_notify(  # type: ignore[arg-type]
                None,
                0,
                "events",
                self._make_payload(user_id=10, row_id=i),
            )
        assert q.full()
        # This should not raise
        self.bus._on_notify(  # type: ignore[arg-type]
            None,
            0,
            "events",
            self._make_payload(user_id=10, row_id=999),
        )
        # Queue is still full, event was dropped
        assert q.full()

    def test_unsubscribe_removes_queue(self) -> None:
        q = self.bus.subscribe(10)
        self.bus.unsubscribe(10, q)
        self.bus._on_notify(None, 0, "events", self._make_payload(user_id=10))  # type: ignore[arg-type]
        assert q.empty()

    def test_subscribe_returns_queue_that_receives_events(self) -> None:
        q = self.bus.subscribe(42)
        self.bus._on_notify(None, 0, "events", self._make_payload(user_id=42))  # type: ignore[arg-type]
        event = q.get_nowait()
        assert event is not None
        assert event.user_id == 42

    def test_multiple_subscribers_same_user(self) -> None:
        q1 = self.bus.subscribe(10)
        q2 = self.bus.subscribe(10)
        self.bus._on_notify(None, 0, "events", self._make_payload(user_id=10))  # type: ignore[arg-type]
        assert not q1.empty()
        assert not q2.empty()

    @pytest.mark.asyncio
    async def test_stop_sends_sentinel(self) -> None:
        q = self.bus.subscribe(10)
        await self.bus.stop()
        item = q.get_nowait()
        assert item is None

    def test_empty_tab_id(self) -> None:
        q = self.bus.subscribe(10)
        payload = json.dumps({"t": "todos", "op": "U", "id": 5, "uid": 10})
        self.bus._on_notify(None, 0, "events", payload)  # type: ignore[arg-type]
        event = q.get_nowait()
        assert event is not None
        assert event.tab_id == ""


# ---------------------------------------------------------------------------
# Integration tests for SSE endpoint
# ---------------------------------------------------------------------------


class TestSSEEndpoint:
    """Test the /api/events/stream endpoint."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client) -> None:
        response = await client.get("/api/events/stream")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticated_returns_event_stream(
        self, authenticated_client
    ) -> None:
        # The SSE endpoint streams forever, so we use a timeout to
        # verify the response starts correctly then bail out.
        async def _check_stream() -> None:
            async with authenticated_client.stream(
                "GET", "/api/events/stream"
            ) as response:
                assert response.status_code == 200
                ct = response.headers.get("content-type", "")
                assert "text/event-stream" in ct

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(_check_stream(), timeout=1.0)
