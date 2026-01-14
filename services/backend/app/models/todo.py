"""Todo model."""

import enum
from datetime import datetime, date

from sqlalchemy import (
    String,
    Text,
    DateTime,
    Date,
    ForeignKey,
    Enum,
    Integer,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Priority(str, enum.Enum):
    """Task priority levels."""

    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Status(str, enum.Enum):
    """Task status values."""

    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class Todo(Base):
    """Todo/task model."""

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum"), default=Priority.medium
    )
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="status_enum"), default=Status.pending
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    actual_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[str | None] = mapped_column(String(50))
    deleted_at: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="todos")  # noqa: F821
    project: Mapped["Project | None"] = relationship(  # noqa: F821
        "Project", back_populates="todos"
    )
