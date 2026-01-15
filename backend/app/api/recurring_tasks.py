"""Recurring tasks API routes."""

from datetime import date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.errors import errors
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
from app.models.recurring_task import Frequency, RecurringTask

router = APIRouter(prefix="/api/recurring-tasks", tags=["recurring-tasks"])


# Schemas
class RecurringTaskCreate(BaseModel):
    """Create recurring task request."""

    title: str = Field(..., min_length=1, max_length=500)
    frequency: Frequency
    start_date: date
    interval_value: int = 1
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    end_date: date | None = None
    project_id: int | None = None
    description: str | None = None
    priority: str = "medium"
    estimated_hours: float | None = None
    tags: list[str] = Field(default_factory=list)
    context: str | None = "work"
    skip_missed: bool = True

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        """Validate weekdays are 0-6."""
        if v is not None:
            for day in v:
                if not isinstance(day, int) or day < 0 or day > 6:
                    raise ValueError(
                        "Weekdays must contain integers 0-6 (Sunday-Saturday)"
                    )
        return v

    @field_validator("day_of_month")
    @classmethod
    def validate_day_of_month(cls, v: int | None) -> int | None:
        """Validate day of month is 1-31."""
        if v is not None and (not isinstance(v, int) or v < 1 or v > 31):
            raise ValueError("Day of month must be an integer 1-31")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        """Validate priority value."""
        valid = ["low", "medium", "high", "urgent"]
        if v not in valid:
            raise ValueError(f"Priority must be one of: {', '.join(valid)}")
        return v


class RecurringTaskUpdate(BaseModel):
    """Update recurring task request."""

    title: str | None = None
    frequency: Frequency | None = None
    interval_value: int | None = None
    weekdays: list[int] | None = None
    day_of_month: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    next_due_date: date | None = None
    project_id: int | None = None
    description: str | None = None
    priority: str | None = None
    estimated_hours: float | None = None
    tags: list[str] | None = None
    context: str | None = None
    skip_missed: bool | None = None
    is_active: bool | None = None

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, v: list[int] | None) -> list[int] | None:
        """Validate weekdays are 0-6."""
        if v is not None:
            for day in v:
                if not isinstance(day, int) or day < 0 or day > 6:
                    raise ValueError(
                        "Weekdays must contain integers 0-6 (Sunday-Saturday)"
                    )
        return v

    @field_validator("day_of_month")
    @classmethod
    def validate_day_of_month(cls, v: int | None) -> int | None:
        """Validate day of month is 1-31."""
        if v is not None and (not isinstance(v, int) or v < 1 or v > 31):
            raise ValueError("Day of month must be an integer 1-31")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        """Validate priority value."""
        if v is not None:
            valid = ["low", "medium", "high", "urgent"]
            if v not in valid:
                raise ValueError(f"Priority must be one of: {', '.join(valid)}")
        return v


class RecurringTaskResponse(BaseModel):
    """Recurring task response."""

    id: int
    title: str
    frequency: Frequency
    interval_value: int
    weekdays: list[int] | None
    day_of_month: int | None
    start_date: date
    end_date: date | None
    next_due_date: date
    project_id: int | None
    description: str | None
    priority: str
    estimated_hours: float | None
    tags: list[str]
    context: str | None
    skip_missed: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class RecurringTaskListResponse(BaseModel):
    """Recurring tasks list response."""

    recurring_tasks: list[RecurringTaskResponse]


@router.get("")
async def list_recurring_tasks(
    user: CurrentUser,
    db: DbSession,
    active_only: bool = Query(True),
) -> RecurringTaskListResponse:
    """List all recurring tasks for the authenticated user."""
    query = select(RecurringTask).where(RecurringTask.user_id == user.id)

    if active_only:
        query = query.where(RecurringTask.is_active == True)  # noqa: E712

    query = query.order_by(RecurringTask.next_due_date.asc())

    result = await db.execute(query)
    tasks = result.scalars().all()

    return RecurringTaskListResponse(
        recurring_tasks=[
            RecurringTaskResponse(
                id=task.id,
                title=task.title,
                frequency=task.frequency,
                interval_value=task.interval_value,
                weekdays=task.weekdays,
                day_of_month=task.day_of_month,
                start_date=task.start_date,
                end_date=task.end_date,
                next_due_date=task.next_due_date,
                project_id=task.project_id,
                description=task.description,
                priority=task.priority,
                estimated_hours=float(task.estimated_hours)
                if task.estimated_hours
                else None,
                tags=task.tags or [],
                context=task.context,
                skip_missed=task.skip_missed,
                is_active=task.is_active,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            for task in tasks
        ]
    )


@router.post("", status_code=201)
async def create_recurring_task(
    request: RecurringTaskCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new recurring task."""
    # Verify project exists if provided
    if request.project_id:
        result = await db.execute(
            select(Project).where(
                Project.id == request.project_id,
                Project.user_id == user.id,
            )
        )
        project = result.scalar_one_or_none()
        if not project:
            raise errors.project_not_found()

    # Calculate initial next_due_date (same as start_date)
    next_due_date = request.start_date

    task = RecurringTask(
        user_id=user.id,
        title=request.title,
        frequency=request.frequency,
        interval_value=request.interval_value,
        weekdays=request.weekdays,
        day_of_month=request.day_of_month,
        start_date=request.start_date,
        end_date=request.end_date,
        next_due_date=next_due_date,
        project_id=request.project_id,
        description=request.description,
        priority=request.priority,
        estimated_hours=request.estimated_hours,
        tags=request.tags,
        context=request.context,
        skip_missed=request.skip_missed,
    )
    db.add(task)
    await db.flush()

    return {
        "data": RecurringTaskResponse(
            id=task.id,
            title=task.title,
            frequency=task.frequency,
            interval_value=task.interval_value,
            weekdays=task.weekdays,
            day_of_month=task.day_of_month,
            start_date=task.start_date,
            end_date=task.end_date,
            next_due_date=task.next_due_date,
            project_id=task.project_id,
            description=task.description,
            priority=task.priority,
            estimated_hours=float(task.estimated_hours)
            if task.estimated_hours
            else None,
            tags=task.tags or [],
            context=task.context,
            skip_missed=task.skip_missed,
            is_active=task.is_active,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    }


@router.get("/{task_id}")
async def get_recurring_task(
    task_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a single recurring task by ID."""
    result = await db.execute(
        select(RecurringTask).where(
            RecurringTask.id == task_id,
            RecurringTask.user_id == user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise errors.recurring_task_not_found()

    return {
        "data": RecurringTaskResponse(
            id=task.id,
            title=task.title,
            frequency=task.frequency,
            interval_value=task.interval_value,
            weekdays=task.weekdays,
            day_of_month=task.day_of_month,
            start_date=task.start_date,
            end_date=task.end_date,
            next_due_date=task.next_due_date,
            project_id=task.project_id,
            description=task.description,
            priority=task.priority,
            estimated_hours=float(task.estimated_hours)
            if task.estimated_hours
            else None,
            tags=task.tags or [],
            context=task.context,
            skip_missed=task.skip_missed,
            is_active=task.is_active,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    }


@router.put("/{task_id}")
async def update_recurring_task(
    task_id: int,
    request: RecurringTaskUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a recurring task."""
    result = await db.execute(
        select(RecurringTask).where(
            RecurringTask.id == task_id,
            RecurringTask.user_id == user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise errors.recurring_task_not_found()

    # Verify project exists if provided
    if request.project_id:
        project_result = await db.execute(
            select(Project).where(
                Project.id == request.project_id,
                Project.user_id == user.id,
            )
        )
        project = project_result.scalar_one_or_none()
        if not project:
            raise errors.project_not_found()

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise errors.validation("No valid fields to update")

    for field, value in update_data.items():
        setattr(task, field, value)

    return {
        "data": RecurringTaskResponse(
            id=task.id,
            title=task.title,
            frequency=task.frequency,
            interval_value=task.interval_value,
            weekdays=task.weekdays,
            day_of_month=task.day_of_month,
            start_date=task.start_date,
            end_date=task.end_date,
            next_due_date=task.next_due_date,
            project_id=task.project_id,
            description=task.description,
            priority=task.priority,
            estimated_hours=float(task.estimated_hours)
            if task.estimated_hours
            else None,
            tags=task.tags or [],
            context=task.context,
            skip_missed=task.skip_missed,
            is_active=task.is_active,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
    }


@router.delete("/{task_id}")
async def delete_recurring_task(
    task_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Deactivate a recurring task (soft delete)."""
    result = await db.execute(
        select(RecurringTask).where(
            RecurringTask.id == task_id,
            RecurringTask.user_id == user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise errors.recurring_task_not_found()

    # Soft delete by setting is_active to False
    task.is_active = False

    return {"data": {"deleted": True}}
