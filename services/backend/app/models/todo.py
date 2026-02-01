"""Todo model."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.attachment import Attachment
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


class AgentStatus(str, enum.Enum):
    """Agent processing status for tasks."""

    pending_review = "pending_review"  # Agent has seen but not processed
    in_progress = "in_progress"  # Agent is actively working on it
    completed = "completed"  # Agent finished its work
    blocked = "blocked"  # Agent cannot proceed (see blocking_reason)
    needs_human = "needs_human"  # Agent determined human action required


class ActionType(str, enum.Enum):
    """Type of action required for the task."""

    research = "research"  # Information gathering, lookups
    code = "code"  # Writing or modifying code
    email = "email"  # Drafting or sending emails
    document = "document"  # Creating or editing documents
    purchase = "purchase"  # Buying something
    schedule = "schedule"  # Scheduling meetings/events
    call = "call"  # Phone calls
    errand = "errand"  # Physical errands
    manual = "manual"  # Requires manual/physical action
    review = "review"  # Reviewing content/code
    data_entry = "data_entry"  # Data entry tasks
    other = "other"  # Uncategorized


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
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("todos.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[Priority] = mapped_column(
        String(20),
        default=Priority.medium,
    )
    status: Mapped[Status] = mapped_column(
        String(20),
        default=Status.pending,
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    actual_hours: Mapped[float | None] = mapped_column(Numeric(5, 2))
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    context: Mapped[str | None] = mapped_column(String(50))
    time_horizon: Mapped[TimeHorizon | None] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Agent integration fields
    agent_actionable: Mapped[bool | None] = mapped_column(
        Boolean, default=None
    )  # True if agent can complete without human
    action_type: Mapped[ActionType | None] = mapped_column(
        String(20)
    )  # Type of action required
    agent_status: Mapped[AgentStatus | None] = mapped_column(
        String(20)
    )  # Agent's processing status
    agent_notes: Mapped[str | None] = mapped_column(
        Text
    )  # Agent-generated context/research
    blocking_reason: Mapped[str | None] = mapped_column(
        String(500)
    )  # Why agent can't proceed

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="todos")
    project: Mapped[Project | None] = relationship("Project", back_populates="todos")
    recurring_task: Mapped[RecurringTask | None] = relationship(
        "RecurringTask", back_populates="generated_todos"
    )
    parent: Mapped[Todo | None] = relationship(
        "Todo", remote_side=[id], back_populates="subtasks"
    )
    subtasks: Mapped[list[Todo]] = relationship(
        "Todo", back_populates="parent", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment", back_populates="todo", cascade="all, delete-orphan"
    )
