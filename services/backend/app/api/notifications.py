"""Notification API routes."""

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select, update
from sqlalchemy import func as sa_func

from app.core.errors import errors
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.notification import Notification
from app.schemas import DataResponse, ListResponse

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notification_type: str
    title: str
    message: str
    wiki_page_id: int | None = None
    is_read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    count: int


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    user: CurrentUserFlexible,
    db: DbSession,
    unread_only: bool = Query(
        False, description="Only return unread notifications"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ListResponse[NotificationResponse]:
    """List notifications for the current user."""
    query = select(Notification).where(
        Notification.user_id == user.id
    )
    if unread_only:
        query = query.where(Notification.is_read.is_(False))
    query = (
        query.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    count_query = select(sa_func.count(Notification.id)).where(
        Notification.user_id == user.id
    )
    if unread_only:
        count_query = count_query.where(
            Notification.is_read.is_(False)
        )

    result = await db.execute(query)
    notifications = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return ListResponse(
        data=[
            NotificationResponse.model_validate(n)
            for n in notifications
        ],
        meta={"count": total},
    )


@router.get("/unread-count")
async def get_unread_count(
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[UnreadCountResponse]:
    """Get count of unread notifications."""
    result = await db.execute(
        select(sa_func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    )
    count = result.scalar() or 0
    return DataResponse(data=UnreadCountResponse(count=count))


@router.put("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[NotificationResponse]:
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise errors.not_found("Notification")

    notification.is_read = True
    await db.flush()
    await db.refresh(notification)
    return DataResponse(
        data=NotificationResponse.model_validate(notification)
    )


@router.put("/read-all")
async def mark_all_read(
    user: CurrentUserFlexible,
    db: DbSession,
) -> DataResponse[dict]:
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.flush()
    return DataResponse(data={"marked_read": True})


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Delete a notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise errors.not_found("Notification")

    await db.execute(
        delete(Notification).where(
            Notification.id == notification_id
        )
    )
    return {"data": {"deleted": True, "id": notification_id}}
