"""Article interaction model."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.user import User


class ArticleRating(str, enum.Enum):
    """Article rating values."""

    good = "good"
    bad = "bad"
    not_interested = "not_interested"


class ArticleInteraction(Base):
    """User interactions with articles (read status, ratings)."""

    __tablename__ = "article_interactions"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE")
    )
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[ArticleRating | None] = mapped_column(String(20))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="article_interactions")
    article: Mapped[Article] = relationship("Article", back_populates="interactions")
