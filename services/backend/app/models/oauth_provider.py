"""OAuth provider model for social login integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserOAuthProvider(Base):
    """Stores OAuth provider connections for users.

    Allows users to link multiple OAuth providers (GitHub, Google, etc.)
    to their account for social login.
    """

    __tablename__ = "user_oauth_providers"
    __table_args__ = (
        # Each user can only have one connection per provider
        UniqueConstraint("user_id", "provider", name="uq_user_oauth_provider"),
        # Provider user ID must be unique per provider
        UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(50), index=True)
    provider_user_id: Mapped[str] = mapped_column(String(255))
    provider_username: Mapped[str | None] = mapped_column(String(255))
    provider_email: Mapped[str | None] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    access_token: Mapped[str | None] = mapped_column(String(500))
    refresh_token: Mapped[str | None] = mapped_column(String(500))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    user: Mapped[User] = relationship("User", back_populates="oauth_providers")
