"""OAuth 2.0 models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class OAuthClient(Base):
    """OAuth 2.0 client registration."""

    __tablename__ = "oauth_clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    client_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    redirect_uris: Mapped[str] = mapped_column(Text)  # JSON stored as text
    grant_types: Mapped[str] = mapped_column(Text, default='["authorization_code"]')
    scopes: Mapped[str] = mapped_column(Text, default='["read"]')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="oauth_clients")


class AuthorizationCode(Base):
    """OAuth 2.0 authorization code."""

    __tablename__ = "authorization_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    redirect_uri: Mapped[str] = mapped_column(String(500))
    scopes: Mapped[str] = mapped_column(Text)  # JSON stored as text
    code_challenge: Mapped[str | None] = mapped_column(String(255))
    code_challenge_method: Mapped[str | None] = mapped_column(String(10))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AccessToken(Base):
    """OAuth 2.0 access token."""

    __tablename__ = "access_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    scopes: Mapped[str] = mapped_column(Text)  # JSON stored as text
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Refresh token (nullable for client credentials grants)
    refresh_token: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class DeviceCode(Base):
    """OAuth 2.0 device authorization (RFC 8628)."""

    __tablename__ = "device_authorization_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(255), index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    scopes: Mapped[str] = mapped_column(Text)  # JSON stored as text
    status: Mapped[str] = mapped_column(String(20), default="pending")
    interval: Mapped[int] = mapped_column(default=5)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
