"""Notification and wiki subscription models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.wiki_page import WikiPage


class NotificationType(enum.StrEnum):
    """Types of notifications."""

    WIKI_PAGE_UPDATED = "wiki_page_updated"
    WIKI_PAGE_CREATED = "wiki_page_created"
    WIKI_PAGE_DELETED = "wiki_page_deleted"


class WikiPageSubscription(Base):
    """Tracks user subscriptions to wiki pages."""

    __tablename__ = "wiki_page_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "wiki_page_id",
            name="uq_wiki_subscription_user_page",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    wiki_page_id: Mapped[int] = mapped_column(
        ForeignKey("wiki_pages.id", ondelete="CASCADE"), index=True
    )
    include_children: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User")
    wiki_page: Mapped[WikiPage] = relationship("WikiPage")


class Notification(Base):
    """In-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        String(30)
    )
    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    wiki_page_id: Mapped[int | None] = mapped_column(
        ForeignKey("wiki_pages.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User")
    wiki_page: Mapped[WikiPage | None] = relationship("WikiPage")
