"""User model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.article_interaction import ArticleInteraction
    from app.models.attachment import Attachment
    from app.models.oauth import OAuthClient
    from app.models.project import Project
    from app.models.recurring_task import RecurringTask
    from app.models.registration_code import RegistrationCode
    from app.models.session import Session
    from app.models.todo import Todo


class User(Base):
    """User account model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    todos: Mapped[list[Todo]] = relationship(
        "Todo", back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        "Project", back_populates="user", cascade="all, delete-orphan"
    )
    oauth_clients: Mapped[list[OAuthClient]] = relationship(
        "OAuthClient", back_populates="user", cascade="all, delete-orphan"
    )
    recurring_tasks: Mapped[list[RecurringTask]] = relationship(
        "RecurringTask", back_populates="user", cascade="all, delete-orphan"
    )
    registration_codes: Mapped[list[RegistrationCode]] = relationship(
        "RegistrationCode", back_populates="created_by"
    )
    article_interactions: Mapped[list[ArticleInteraction]] = relationship(
        "ArticleInteraction", back_populates="user", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment", back_populates="user", cascade="all, delete-orphan"
    )
