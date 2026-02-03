"""Project API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func, select

from app.core.errors import errors
from app.db.queries import (
    get_next_position,
    get_resource_for_user,
    get_resources_for_user,
)
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.project import Project
from app.models.todo import Status, Todo
from app.schemas import ListResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


# Schemas
class ProjectCreate(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    color: str = "#3b82f6"
    position: int | None = None


class ProjectUpdate(BaseModel):
    """Update project request.

    Note: archived_at is not settable via update - use /archive and /unarchive.
    """

    name: str | None = None
    description: str | None = None
    color: str | None = None
    position: int | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    """Project response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    color: str
    position: int
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


class ProjectStats(BaseModel):
    """Statistics for a project."""

    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    cancelled_tasks: int
    completion_percentage: float
    total_estimated_hours: float | None
    total_actual_hours: float | None
    overdue_tasks: int


class ProjectWithStats(ProjectResponse):
    """Project response with statistics."""

    stats: ProjectStats | None = None


async def _get_project_stats(
    db: DbSession, project_ids: list[int]
) -> dict[int, ProjectStats]:
    """Get statistics for multiple projects in a single query.

    Only counts top-level tasks (parent_id IS NULL) to avoid double-counting subtasks.
    """
    from datetime import date

    today = date.today()

    # Build the aggregation query
    stats_query = (
        select(
            Todo.project_id,
            func.count(Todo.id).label("total_tasks"),
            func.sum(case((Todo.status == Status.completed, 1), else_=0)).label(
                "completed_tasks"
            ),
            func.sum(case((Todo.status == Status.pending, 1), else_=0)).label(
                "pending_tasks"
            ),
            func.sum(case((Todo.status == Status.in_progress, 1), else_=0)).label(
                "in_progress_tasks"
            ),
            func.sum(case((Todo.status == Status.cancelled, 1), else_=0)).label(
                "cancelled_tasks"
            ),
            func.sum(Todo.estimated_hours).label("total_estimated_hours"),
            func.sum(Todo.actual_hours).label("total_actual_hours"),
            func.sum(
                case(
                    (
                        (Todo.due_date < today)
                        & (Todo.status.in_([Status.pending, Status.in_progress])),
                        1,
                    ),
                    else_=0,
                )
            ).label("overdue_tasks"),
        )
        .where(
            Todo.project_id.in_(project_ids),
            Todo.deleted_at.is_(None),
            Todo.parent_id.is_(None),  # Only top-level tasks
        )
        .group_by(Todo.project_id)
    )

    result = await db.execute(stats_query)
    rows = result.all()

    stats_by_project: dict[int, ProjectStats] = {}
    for row in rows:
        total = row.total_tasks or 0
        completed = row.completed_tasks or 0
        percentage = (completed / total * 100) if total > 0 else 0.0

        stats_by_project[row.project_id] = ProjectStats(
            total_tasks=total,
            completed_tasks=completed,
            pending_tasks=row.pending_tasks or 0,
            in_progress_tasks=row.in_progress_tasks or 0,
            cancelled_tasks=row.cancelled_tasks or 0,
            completion_percentage=round(percentage, 1),
            total_estimated_hours=(
                float(row.total_estimated_hours) if row.total_estimated_hours else None
            ),
            total_actual_hours=(
                float(row.total_actual_hours) if row.total_actual_hours else None
            ),
            overdue_tasks=row.overdue_tasks or 0,
        )

    # Add empty stats for projects with no tasks
    for project_id in project_ids:
        if project_id not in stats_by_project:
            stats_by_project[project_id] = ProjectStats(
                total_tasks=0,
                completed_tasks=0,
                pending_tasks=0,
                in_progress_tasks=0,
                cancelled_tasks=0,
                completion_percentage=0.0,
                total_estimated_hours=None,
                total_actual_hours=None,
                overdue_tasks=0,
            )

    return stats_by_project


@router.get("")
async def list_projects(
    user: CurrentUserFlexible,
    db: DbSession,
    include_archived: bool = False,
    include_stats: bool = False,
) -> ListResponse[ProjectResponse] | ListResponse[ProjectWithStats]:
    """List all projects for the user, ordered by position.

    Args:
        include_archived: Include archived projects in the response.
        include_stats: Include task statistics (counts, completion %) for each project.
    """
    query = select(Project).where(Project.user_id == user.id)

    if not include_archived:
        query = query.where(Project.archived_at.is_(None))

    query = query.order_by(Project.position, Project.name)
    result = await db.execute(query)
    projects = result.scalars().all()

    if include_stats:
        project_ids = [p.id for p in projects]
        if project_ids:
            stats_by_project = await _get_project_stats(db, project_ids)
        else:
            stats_by_project = {}

        return ListResponse(
            data=[
                ProjectWithStats(
                    **ProjectResponse.model_validate(p).model_dump(),
                    stats=stats_by_project.get(p.id),
                )
                for p in projects
            ],
            meta={"count": len(projects)},
        )

    return ListResponse(
        data=[ProjectResponse.model_validate(p) for p in projects],
        meta={"count": len(projects)},
    )


@router.post("", status_code=201)
async def create_project(
    request: ProjectCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Create a new project."""
    # Auto-assign position if not provided
    position = request.position
    if position is None:
        position = await get_next_position(db, Project, user.id)

    project = Project(
        user_id=user.id,
        name=request.name,
        description=request.description,
        color=request.color,
        position=position,
    )
    db.add(project)
    await db.flush()

    return {"data": ProjectResponse.model_validate(project)}


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
    include_stats: bool = False,
) -> dict:
    """Get a project by ID.

    Args:
        include_stats: Include task statistics for this project.
    """
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    if include_stats:
        stats_by_project = await _get_project_stats(db, [project_id])
        return {
            "data": ProjectWithStats(
                **ProjectResponse.model_validate(project).model_dump(),
                stats=stats_by_project.get(project_id),
            )
        }

    return {"data": ProjectResponse.model_validate(project)}


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Get task statistics for a project."""
    # Verify project exists and belongs to user
    await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    stats_by_project = await _get_project_stats(db, [project_id])
    return {"data": stats_by_project.get(project_id)}


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Update a project."""
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    return {"data": ProjectResponse.model_validate(project)}


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Delete a project."""
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    await db.delete(project)

    return {"data": {"deleted": True}}


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Archive a project."""
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    project.archived_at = datetime.now(UTC)

    return {"data": ProjectResponse.model_validate(project)}


@router.post("/{project_id}/unarchive")
async def unarchive_project(
    project_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Unarchive a project."""
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    project.archived_at = None

    return {"data": ProjectResponse.model_validate(project)}


class ReorderRequest(BaseModel):
    """Reorder projects request."""

    project_ids: list[int] = Field(..., min_length=1)


@router.post("/reorder")
async def reorder_projects(
    request: ReorderRequest,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Reorder projects by providing the new order of project IDs."""
    # Fetch all projects for user
    projects = await get_resources_for_user(
        db, Project, request.project_ids, user.id, check_deleted=False
    )

    # Validate all requested IDs were found and belong to user
    if len(projects) != len(request.project_ids):
        missing_ids = set(request.project_ids) - set(projects.keys())
        raise errors.not_found(f"Projects not found: {missing_ids}")

    # Update positions based on order in the list
    for position, project_id in enumerate(request.project_ids):
        projects[project_id].position = position

    return {"data": {"reordered": len(projects)}}
