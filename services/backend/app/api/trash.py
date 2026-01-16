"""Trash API routes for managing deleted todos."""

from datetime import date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.errors import errors
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
from app.models.todo import Todo

router = APIRouter(prefix="/api/trash", tags=["trash"])


# Schemas
class DeletedTodoResponse(BaseModel):
    """Deleted todo response."""

    id: int
    title: str
    description: str | None
    due_date: date | None
    status: str
    project_name: str | None
    project_color: str | None
    priority: str
    tags: list[str]
    deleted_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class TrashListResponse(BaseModel):
    """Trash list response."""

    data: list[DeletedTodoResponse]
    meta: dict


@router.get("")
async def list_deleted_todos(
    user: CurrentUser,
    db: DbSession,
    query: str | None = Query(None),
) -> TrashListResponse:
    """List all deleted todos for the current user."""
    stmt = (
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(Todo.user_id == user.id)
        .where(Todo.deleted_at.is_not(None))
        .order_by(Todo.deleted_at.desc())
    )

    # Apply search filter if query provided
    if query and query.strip():
        search_term = f"%{query.strip()}%"
        stmt = stmt.where(
            (Todo.title.ilike(search_term)) | (Todo.description.ilike(search_term))
        )

    result = await db.execute(stmt)
    rows = result.all()

    tasks = []
    for row in rows:
        todo = row[0]
        tasks.append(
            DeletedTodoResponse(
                id=todo.id,
                title=todo.title,
                description=todo.description,
                due_date=todo.due_date,
                status=(
                    todo.status if isinstance(todo.status, str) else todo.status.value
                ),
                project_name=row.project_name,
                project_color=row.project_color,
                priority=(
                    todo.priority
                    if isinstance(todo.priority, str)
                    else todo.priority.value
                ),
                tags=todo.tags or [],
                deleted_at=todo.deleted_at,
                created_at=todo.created_at,
            )
        )

    return TrashListResponse(data=tasks, meta={"count": len(tasks)})


@router.post("/{todo_id}/restore")
async def restore_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Restore a deleted todo."""
    result = await db.execute(
        select(Todo).where(
            Todo.id == todo_id,
            Todo.user_id == user.id,
            Todo.deleted_at.is_not(None),
        )
    )
    todo = result.scalar_one_or_none()

    if not todo:
        raise errors.not_found("Deleted task")

    # Restore by clearing deleted_at
    todo.deleted_at = None

    return {"data": {"restored": True, "id": todo.id}}
