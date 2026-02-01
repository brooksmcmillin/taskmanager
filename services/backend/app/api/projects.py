"""Project API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import errors
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
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


@router.get("")
async def list_projects(
    user: CurrentUser,
    db: DbSession,
    include_archived: bool = False,
) -> ListResponse[ProjectResponse]:
    """List all projects for the user, ordered by position."""
    query = select(Project).where(Project.user_id == user.id)

    if not include_archived:
        query = query.where(Project.archived_at.is_(None))

    query = query.order_by(Project.position, Project.name)
    result = await db.execute(query)
    projects = result.scalars().all()

    return ListResponse(
        data=[ProjectResponse.model_validate(p) for p in projects],
        meta={"count": len(projects)},
    )


@router.post("", status_code=201)
async def create_project(
    request: ProjectCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new project."""
    # Auto-assign position if not provided
    position = request.position
    if position is None:
        # Get the max position for this user's projects
        from sqlalchemy import func as sql_func

        max_pos_result = await db.execute(
            select(sql_func.max(Project.position)).where(Project.user_id == user.id)
        )
        max_pos = max_pos_result.scalar() or 0
        position = max_pos + 1

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
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a project by ID."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise errors.project_not_found()

    return {"data": ProjectResponse.model_validate(project)}


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    request: ProjectUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise errors.project_not_found()

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    return {"data": ProjectResponse.model_validate(project)}


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise errors.project_not_found()

    await db.delete(project)

    return {"data": {"deleted": True}}


@router.post("/{project_id}/archive")
async def archive_project(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Archive a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise errors.project_not_found()

    project.archived_at = datetime.now(UTC)

    return {"data": ProjectResponse.model_validate(project)}


@router.post("/{project_id}/unarchive")
async def unarchive_project(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Unarchive a project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise errors.project_not_found()

    project.archived_at = None

    return {"data": ProjectResponse.model_validate(project)}


class ReorderRequest(BaseModel):
    """Reorder projects request."""

    project_ids: list[int] = Field(..., min_length=1)


@router.post("/reorder")
async def reorder_projects(
    request: ReorderRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Reorder projects by providing the new order of project IDs."""
    # Fetch all projects for user
    result = await db.execute(
        select(Project).where(
            Project.id.in_(request.project_ids), Project.user_id == user.id
        )
    )
    projects = {p.id: p for p in result.scalars().all()}

    # Validate all requested IDs were found and belong to user
    if len(projects) != len(request.project_ids):
        missing_ids = set(request.project_ids) - set(projects.keys())
        raise errors.not_found(f"Projects not found: {missing_ids}")

    # Update positions based on order in the list
    for position, project_id in enumerate(request.project_ids):
        projects[project_id].position = position

    return {"data": {"reordered": len(projects)}}
