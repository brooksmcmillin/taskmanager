"""Todo model."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.recurring_task import RecurringTask
    from app.models.user import User


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
    cancelled = "cancelled"


class TimeHorizon(str, enum.Enum):
    """Time horizon for task planning."""

    today = "today"
    this_week = "this_week"
    next_week = "next_week"
    this_month = "this_month"
    next_month = "next_month"
    this_quarter = "this_quarter"
    next_quarter = "next_quarter"
    this_year = "this_year"
    next_year = "next_year"
    someday = "someday"


class Todo(Base):
    """Todo/task model."""

    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    recurring_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_tasks.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, name="priority_enum", create_constraint=False),
        default=Priority.medium,
    )
    status: Mapped[Status] = mapped_column(
        Enum(Status, name="status_enum", create_constraint=False),
        default=Status.pending,
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    actual_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[str | None] = mapped_column(String(50))
    time_horizon: Mapped[TimeHorizon | None] = mapped_column(
        Enum(TimeHorizon, name="time_horizon_enum", create_constraint=False)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="todos")
    project: Mapped[Project | None] = relationship("Project", back_populates="todos")
    recurring_task: Mapped[RecurringTask | None] = relationship(
        "RecurringTask", back_populates="generated_todos"
    )
