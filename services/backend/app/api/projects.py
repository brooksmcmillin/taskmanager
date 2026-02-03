"""Project API routes."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import errors
from app.db.queries import (
    get_next_position,
    get_resource_for_user,
    get_resources_for_user,
)
from app.dependencies import CurrentUserFlexible, DbSession
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
    user: CurrentUserFlexible,
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
) -> dict:
    """Get a project by ID."""
    project = await get_resource_for_user(
        db, Project, project_id, user.id, errors.project_not_found, check_deleted=False
    )

    return {"data": ProjectResponse.model_validate(project)}


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
