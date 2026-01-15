"""Todo API routes."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select

from app.core.errors import errors
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
from app.models.todo import Priority, Status, Todo

router = APIRouter(prefix="/api/todos", tags=["todos"])


# Schemas
class TodoCreate(BaseModel):
    """Create todo request."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Priority = Priority.medium
    status: Status = Status.pending
    due_date: date | None = None
    project_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    context: str | None = None
    estimated_hours: float | None = None


class TodoUpdate(BaseModel):
    """Update todo request."""

    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    status: Status | None = None
    due_date: date | None = None
    project_id: int | None = None
    tags: list[str] | None = None
    context: str | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None


class BulkUpdateRequest(BaseModel):
    """Bulk update request."""

    ids: list[int]
    updates: TodoUpdate


class TodoResponse(BaseModel):
    """Todo response."""

    id: int
    title: str
    description: str | None
    priority: Priority
    status: Status
    due_date: date | None
    project_id: int | None
    project_name: str | None = None
    project_color: str | None = None
    tags: list[str]
    context: str | None
    estimated_hours: float | None
    actual_hours: float | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class TodoListResponse(BaseModel):
    """Todo list response."""

    tasks: list[TodoResponse]
    meta: dict


@router.get("")
async def list_todos(
    user: CurrentUser,
    db: DbSession,
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    category: str | None = Query(None),
    start_date: date | None = Query(None),  # noqa: B008
    end_date: date | None = Query(None),  # noqa: B008
) -> TodoListResponse:
    """List todos with optional filters."""
    query = (
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(Todo.user_id == user.id)
        .where(Todo.deleted_at.is_(None))
    )

    # Apply filters
    if status and status != "all":
        if status == "overdue":
            query = query.where(
                and_(
                    Todo.due_date < date.today(),
                    Todo.status != Status.completed,
                )
            )
        else:
            query = query.where(Todo.status == status)

    if project_id:
        query = query.where(Todo.project_id == project_id)

    if category:
        query = query.join(Project).where(Project.name == category)

    if start_date:
        query = query.where(Todo.due_date >= start_date)

    if end_date:
        query = query.where(Todo.due_date <= end_date)

    query = query.order_by(Todo.due_date.asc().nulls_last(), Todo.priority.desc())

    result = await db.execute(query)
    rows = result.all()

    tasks = []
    for row in rows:
        todo = row[0]
        tasks.append(
            TodoResponse(
                id=todo.id,
                title=todo.title,
                description=todo.description,
                priority=todo.priority,
                status=todo.status,
                due_date=todo.due_date,
                project_id=todo.project_id,
                project_name=row.project_name,
                project_color=row.project_color,
                tags=todo.tags or [],
                context=todo.context,
                estimated_hours=float(todo.estimated_hours)
                if todo.estimated_hours
                else None,
                actual_hours=float(todo.actual_hours) if todo.actual_hours else None,
                created_at=todo.created_at,
                updated_at=todo.updated_at,
            )
        )

    return TodoListResponse(tasks=tasks, meta={"count": len(tasks)})


@router.post("", status_code=201)
async def create_todo(
    request: TodoCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new todo."""
    todo = Todo(
        user_id=user.id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        status=request.status,
        due_date=request.due_date,
        project_id=request.project_id,
        tags=request.tags,
        context=request.context,
        estimated_hours=request.estimated_hours,
    )
    db.add(todo)
    await db.flush()

    return {"data": {"id": todo.id, "title": todo.title}}


@router.get("/{todo_id}")
async def get_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a todo by ID."""
    result = await db.execute(
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(Todo.id == todo_id, Todo.user_id == user.id)
    )
    row = result.one_or_none()

    if not row:
        raise errors.todo_not_found()

    todo = row[0]
    return {
        "data": TodoResponse(
            id=todo.id,
            title=todo.title,
            description=todo.description,
            priority=todo.priority,
            status=todo.status,
            due_date=todo.due_date,
            project_id=todo.project_id,
            project_name=row.project_name,
            project_color=row.project_color,
            tags=todo.tags or [],
            context=todo.context,
            estimated_hours=float(todo.estimated_hours)
            if todo.estimated_hours
            else None,
            actual_hours=float(todo.actual_hours) if todo.actual_hours else None,
            created_at=todo.created_at,
            updated_at=todo.updated_at,
        )
    }


@router.put("/{todo_id}")
async def update_todo(
    todo_id: int,
    request: TodoUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a todo."""
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user.id)
    )
    todo = result.scalar_one_or_none()

    if not todo:
        raise errors.todo_not_found()

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(todo, field, value)

    return {"data": {"id": todo.id, "updated": True}}


@router.put("")
async def bulk_update_todos(
    request: BulkUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Bulk update todos."""
    result = await db.execute(
        select(Todo).where(Todo.id.in_(request.ids), Todo.user_id == user.id)
    )
    todos = result.scalars().all()

    update_data = request.updates.model_dump(exclude_unset=True)
    for todo in todos:
        for field, value in update_data.items():
            setattr(todo, field, value)

    return {"data": {"updated": len(todos)}}


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Soft delete a todo."""
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user.id)
    )
    todo = result.scalar_one_or_none()

    if not todo:
        raise errors.todo_not_found()

    todo.deleted_at = date.today()

    return {"data": {"deleted": True}}


@router.post("/{todo_id}/complete")
async def complete_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Mark a todo as complete."""
    result = await db.execute(
        select(Todo).where(Todo.id == todo_id, Todo.user_id == user.id)
    )
    todo = result.scalar_one_or_none()

    if not todo:
        raise errors.todo_not_found()

    todo.status = Status.completed
    todo.completed_date = datetime.now(UTC)

    return {"data": {"completed": True}}
