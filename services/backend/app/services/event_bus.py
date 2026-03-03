"""Real-time event bus using PostgreSQL LISTEN/NOTIFY.

Opens a dedicated asyncpg connection (separate from SQLAlchemy's pool) and
dispatches row-change events to per-user asyncio.Queue subscribers.

On connection loss the bus automatically reconnects with exponential backoff
and sends a sentinel to all subscribers so SSE clients reconnect.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)

_RECONNECT_BASE = 1.0  # seconds
_RECONNECT_MAX = 30.0


@dataclass(frozen=True, slots=True)
class Event:
    """Parsed event from a PG NOTIFY payload."""

    table: str  # e.g. "todos"
    op: str  # I / U / D
    id: int  # row PK
    user_id: int  # owner
    tab_id: str  # originating browser tab


class EventBus:
    """Singleton event bus backed by PG LISTEN/NOTIFY."""

    def __init__(self) -> None:
        self._conn: asyncpg.Connection | None = None
        self._subscribers: dict[int, set[asyncio.Queue[Event | None]]] = {}
        self._stopping = False
        self._reconnect_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Open a connection, register listeners."""
        conn = await asyncpg.connect(
            user=settings.postgres_user,
            password=settings.postgres_password,
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            ssl="prefer",
        )
        conn.add_termination_listener(self._on_connection_lost)
        await conn.add_listener("events", self._on_notify)
        self._conn = conn
        logger.info("EventBus connected — listening on 'events' channel")

    async def start(self) -> None:
        """Open a dedicated connection and start listening."""
        self._stopping = False
        try:
            await self._connect()
        except Exception:
            logger.exception("EventBus failed to start — will retry")
            self._schedule_reconnect()

    async def stop(self) -> None:
        """Stop listening and close the connection."""
        self._stopping = True

        # Cancel any pending reconnect
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task
            self._reconnect_task = None

        if self._conn is not None:
            try:
                await self._conn.remove_listener("events", self._on_notify)
                await self._conn.close()
            except Exception:
                logger.exception("Error closing EventBus connection")
            finally:
                self._conn = None

        # Send sentinel to all subscribers so SSE generators exit cleanly
        self._send_sentinel_to_all()
        self._subscribers.clear()
        logger.info("EventBus stopped")

    # ------------------------------------------------------------------
    # Reconnection
    # ------------------------------------------------------------------

    def _on_connection_lost(self, conn: asyncpg.Connection) -> None:
        """Called by asyncpg when the connection drops unexpectedly."""
        logger.warning("EventBus connection lost — scheduling reconnect")
        self._conn = None
        # Notify all subscribers so SSE clients reconnect and reload
        self._send_sentinel_to_all()
        if not self._stopping:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Kick off the reconnect loop as a background task."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # already reconnecting
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Retry connecting with exponential backoff."""
        attempt = 0
        while not self._stopping:
            delay = min(_RECONNECT_BASE * 2**attempt, _RECONNECT_MAX)
            logger.info(
                "EventBus reconnecting in %.1fs (attempt %d)", delay, attempt + 1
            )
            await asyncio.sleep(delay)
            if self._stopping:
                break
            try:
                await self._connect()
                logger.info("EventBus reconnected successfully")
                return
            except Exception:
                logger.exception("EventBus reconnect attempt %d failed", attempt + 1)
                attempt += 1

    def _send_sentinel_to_all(self) -> None:
        """Push None to every subscriber queue so SSE generators exit."""
        for queues in self._subscribers.values():
            for q in queues:
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(None)

    # ------------------------------------------------------------------
    # Subscribe / unsubscribe
    # ------------------------------------------------------------------

    def subscribe(self, user_id: int) -> asyncio.Queue[Event | None]:
        """Register a bounded queue for a user and return it."""
        q: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=256)
        self._subscribers.setdefault(user_id, set()).add(q)
        total = len(self._subscribers.get(user_id, set()))
        logger.debug("User %d subscribed (total queues: %d)", user_id, total)
        return q

    def unsubscribe(self, user_id: int, q: asyncio.Queue[Event | None]) -> None:
        """Remove a queue from the registry."""
        queues = self._subscribers.get(user_id)
        if queues:
            queues.discard(q)
            if not queues:
                del self._subscribers[user_id]
        logger.debug("User %d unsubscribed", user_id)

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _on_notify(
        self,
        conn: asyncpg.Connection,
        pid: int,
        channel: str,
        payload: str,
    ) -> None:
        """Parse NOTIFY payload and dispatch to matching user queues."""
        try:
            data = json.loads(payload)
            event = Event(
                table=data["t"],
                op=data["op"],
                id=data["id"],
                user_id=data["uid"],
                tab_id=data.get("tab", ""),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Malformed event payload: %s", payload)
            return

        queues = self._subscribers.get(event.user_id)
        if not queues:
            return

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Dropping event for user %d — queue full", event.user_id
                )


# Module-level singleton
event_bus = EventBus()
