"""Real-time event bus using PostgreSQL LISTEN/NOTIFY.

Opens a dedicated asyncpg connection (separate from SQLAlchemy's pool) and
dispatches row-change events to per-user asyncio.Queue subscribers.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from urllib.parse import quote_plus

import asyncpg

from app.config import settings

logger = logging.getLogger(__name__)


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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Open a dedicated connection and start listening."""
        dsn = (
            f"postgresql://{settings.postgres_user}"
            f":{quote_plus(settings.postgres_password)}"
            f"@{settings.postgres_host}:{settings.postgres_port}"
            f"/{settings.postgres_db}"
        )
        try:
            self._conn = await asyncpg.connect(dsn, ssl="prefer")
            await self._conn.add_listener("events", self._on_notify)
            logger.info("EventBus started — listening on 'events' channel")
        except Exception:
            logger.exception("EventBus failed to start")
            self._conn = None

    async def stop(self) -> None:
        """Stop listening and close the connection."""
        if self._conn is not None:
            try:
                await self._conn.remove_listener("events", self._on_notify)
                await self._conn.close()
            except Exception:
                logger.exception("Error closing EventBus connection")
            finally:
                self._conn = None

        # Send sentinel to all subscribers so SSE generators exit cleanly
        for queues in self._subscribers.values():
            for q in queues:
                with contextlib.suppress(asyncio.QueueFull):
                    q.put_nowait(None)
        self._subscribers.clear()
        logger.info("EventBus stopped")

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
