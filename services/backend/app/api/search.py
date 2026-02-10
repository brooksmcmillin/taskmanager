"""Search API route."""

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.dependencies import CurrentUserFlexible, DbSession
from app.models.project import Project
from app.models.todo import Todo

router = APIRouter(prefix="/api/tasks", tags=["search"])


@router.get("/search")
async def search_tasks(
    user: CurrentUserFlexible,
    db: DbSession,
    q: str = Query(..., min_length=1),
    category: str | None = Query(None),
) -> dict:
    """Full-text search for tasks.

    Uses PostgreSQL tsvector for efficient searching.
    """
    # Build search query using PostgreSQL full-text search
    search_vector = func.to_tsvector(
        "english",
        func.concat(Todo.title, " ", func.coalesce(Todo.description, "")),
    )
    search_query = func.plainto_tsquery("english", q)

    query = (
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(
            Todo.user_id == user.id,
            Todo.deleted_at.is_(None),
            search_vector.bool_op("@@")(search_query),
        )
    )

    if category:
        query = query.where(Project.name == category)

    query = query.order_by(Todo.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    tasks = [
        {
            "id": row[0].id,
            "title": row[0].title,
            "description": row[0].description,
            "status": row[0].status,
            "priority": row[0].priority,
            "due_date": row[0].due_date.isoformat() if row[0].due_date else None,
            "project_name": row.project_name,
            "project_color": row.project_color,
            "tags": row[0].tags or [],
        }
        for row in rows
    ]

    return {"data": tasks, "meta": {"count": len(tasks)}}
