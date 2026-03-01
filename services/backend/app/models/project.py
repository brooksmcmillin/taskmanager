"""Project model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.todo import Todo
    from app.models.user import User


class Project(Base):
    """Project model for organizing todos."""

    __tablename__ = "projects"
    __table_args__ = (
        # Per-user case-insensitive unique index on project name.
        # Replaces the old global UniqueConstraint("name") to allow different
        # users to have projects with the same name, while still preventing
        # duplicate names (case-insensitively) within the same user.
        Index(
            "uq_projects_user_lower_name",
            text("user_id"),
            text("lower(name)"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    show_on_calendar: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User | None] = relationship("User", back_populates="projects")
    todos: Mapped[list[Todo]] = relationship("Todo", back_populates="project")
