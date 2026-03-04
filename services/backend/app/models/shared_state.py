"""Shared state model for multi-worker compatible key-value storage.

Used for rate limiting counters, OAuth state, and other ephemeral data
that must be shared across multiple application workers.
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SharedState(Base):
    """Key-value store with namespace separation and TTL-based expiration.

    Namespaces:
    - 'rate_limit': Rate limiting attempt timestamps per key
    - 'oauth_state': GitHub OAuth state tokens with return_to data
    """

    __tablename__ = "shared_state"

    namespace: Mapped[str] = mapped_column(String(50), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_shared_state_expires_at", "expires_at"),
        Index("ix_shared_state_namespace_expires", "namespace", "expires_at"),
    )
