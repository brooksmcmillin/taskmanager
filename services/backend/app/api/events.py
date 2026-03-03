"""Server-Sent Events endpoint for real-time updates."""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.dependencies import CurrentUserFlexible
from app.services.event_bus import event_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])

HEARTBEAT_INTERVAL = 30  # seconds


async def _event_generator(
    request: Request, user_id: int
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events for a user."""
    queue = event_bus.subscribe(user_id)
    event_id = 0
    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
            except TimeoutError:
                # Send heartbeat comment to keep connection alive
                yield ": heartbeat\n\n"
                continue

            # None sentinel means server is shutting down
            if event is None:
                break

            event_id += 1
            data = json.dumps(
                {
                    "table": event.table,
                    "op": event.op,
                    "id": event.id,
                    "tab_id": event.tab_id,
                },
                separators=(",", ":"),
            )
            yield f"event: change\ndata: {data}\nid: {event_id}\n\n"

    finally:
        event_bus.unsubscribe(user_id, queue)


@router.get("/stream")
async def event_stream(
    request: Request,
    user: CurrentUserFlexible,
) -> StreamingResponse:
    """SSE stream of real-time change events for the authenticated user."""
    return StreamingResponse(
        _event_generator(request, user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
