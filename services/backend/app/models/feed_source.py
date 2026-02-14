"""Feed source model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.article import Article


class FeedType(str, enum.Enum):
    """Feed source type."""

    paper = "paper"
    article = "article"


class FeedSource(Base):
    """RSS/Atom feed source model."""

    __tablename__ = "feed_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[FeedType] = mapped_column(String(20), default=FeedType.article)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    fetch_interval_hours: Mapped[int] = mapped_column(Integer, default=6)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quality_score: Mapped[float] = mapped_column(default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    articles: Mapped[list[Article]] = relationship(
        "Article", back_populates="feed_source", cascade="all, delete-orphan"
    )
