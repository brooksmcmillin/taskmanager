"""Article model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.article_interaction import ArticleInteraction
    from app.models.feed_source import FeedSource


class Article(Base):
    """News article model."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    feed_source_id: Mapped[int] = mapped_column(
        ForeignKey("feed_sources.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    feed_source: Mapped[FeedSource] = relationship(
        "FeedSource", back_populates="articles"
    )
    interactions: Mapped[list[ArticleInteraction]] = relationship(
        "ArticleInteraction", back_populates="article", cascade="all, delete-orphan"
    )
