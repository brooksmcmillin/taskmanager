"""Recurring task model for generating repeated todos."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.todo import Todo
    from app.models.user import User


class Frequency(str, enum.Enum):
    """Recurrence frequency options."""

    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class RecurringTask(Base):
    """Recurring task template for generating todos on a schedule."""

    __tablename__ = "recurring_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Recurrence pattern
    frequency: Mapped[Frequency] = mapped_column(String(20))
    interval_value: Mapped[int] = mapped_column(Integer, default=1)
    weekdays: Mapped[list[int] | None] = mapped_column(
        ARRAY(Integer)
    )  # For weekly: 0=Sunday, 6=Saturday
    day_of_month: Mapped[int | None] = mapped_column(Integer)

    # Time bounds
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    next_due_date: Mapped[date] = mapped_column(Date)

    # Task template fields (copied to generated todos)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[str | None] = mapped_column(String(50))

    # Behavior control
    skip_missed: Mapped[bool] = mapped_column(
        Boolean, default=True
    )  # true = floating (next from today), false = fixed schedule
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="recurring_tasks")
    project: Mapped[Project | None] = relationship("Project")
    generated_todos: Mapped[list[Todo]] = relationship(
        "Todo", back_populates="recurring_task"
    )
