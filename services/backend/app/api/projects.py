"""Project API routes."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import errors
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


# Schemas
class ProjectCreate(BaseModel):
    """Create project request."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    color: str = "#3b82f6"


class ProjectUpdate(BaseModel):
    """Update project request."""

    name: str | None = None
    description: str | None = None
    color: str | None = None
    is_active: bool | None = None


class ProjectResponse(BaseModel):
    """Project response."""

    id: int
    name: str
    description: str | None
    color: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Project list response."""

    data: list[ProjectResponse]
    meta: dict


@router.get("")
async def list_projects(
    user: CurrentUser,
    db: DbSession,
) -> ProjectListResponse:
    """List all projects for the user."""
    result = await db.execute(
        select(Project).where(Project.user_id == user.id).order_by(Project.name)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
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
    project = Project(
        user_id=user.id,
        name=request.name,
        description=request.description,
        color=request.color,
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
