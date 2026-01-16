"""Categories API route."""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
from app.models.todo import Status, Todo

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
async def get_categories(
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get categories (projects) with task counts."""
    # Query projects with pending task counts
    result = await db.execute(
        select(
            Project.id,
            Project.name,
            Project.color,
            func.count(Todo.id)
            .filter(
                Todo.status != Status.completed,
                Todo.deleted_at.is_(None),
            )
            .label("pending_count"),
        )
        .outerjoin(Todo, Todo.project_id == Project.id)
        .where(Project.user_id == user.id, Project.is_active.is_(True))
        .group_by(Project.id)
        .order_by(Project.name)
    )
    rows = result.all()

    categories = [
        {
            "id": row.id,
            "name": row.name,
            "color": row.color,
            "pending_count": row.pending_count,
        }
        for row in rows
    ]

    return {"data": categories, "meta": {"count": len(categories)}}
