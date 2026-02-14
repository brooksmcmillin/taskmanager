"""Reusable database query helpers.

Provides centralized utilities for common database operations like
authorization checks, soft-delete filtering, and position assignment.

Note on typing: These functions use `Any` for model parameters because
SQLAlchemy models use `Mapped[T]` column descriptors that don't satisfy
simple Protocol definitions. Type safety is ensured at runtime via
`hasattr` checks. All models must have `id` and `user_id` columns.
"""

from collections.abc import Callable
from typing import Any

from sqlalchemy import func as sql_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.models.project import Project


async def get_resource_for_user(
    db: AsyncSession,
    model: Any,
    resource_id: int,
    user_id: int,
    error_factory: Callable[[], ApiError],
    *,
    check_deleted: bool = True,
) -> Any:
    """Get a resource by ID, ensuring it belongs to the user.

    This helper centralizes the common pattern of:
    1. Querying a resource by ID
    2. Verifying user ownership
    3. Optionally checking soft-delete status
    4. Raising a standardized error if not found

    Args:
        db: Database session
        model: SQLAlchemy model class (must have id and user_id columns)
        resource_id: Resource ID to fetch
        user_id: User ID for authorization check
        error_factory: Error factory function (e.g., errors.todo_not_found)
        check_deleted: Whether to filter by deleted_at (default True).
                       Only applies if model has a deleted_at column.

    Returns:
        Model instance

    Raises:
        ApiError: From error_factory if resource not found or unauthorized

    Example:
        todo = await get_resource_for_user(
            db, Todo, todo_id, user.id, errors.todo_not_found
        )
    """
    query = select(model).where(
        model.id == resource_id,
        model.user_id == user_id,
    )
    if check_deleted and hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    resource = result.scalar_one_or_none()
    if not resource:
        raise error_factory()
    return resource


async def get_next_position(
    db: AsyncSession,
    model: Any,
    user_id: int,
    *,
    parent_id: int | None = None,
    check_deleted: bool = True,
    extra_filters: list[Any] | None = None,
) -> int:
    """Get the next position value for ordering.

    Calculates max(position) + 1 for a given model scoped to the user.
    Handles hierarchical models (with parent_id) and soft-deleted records.

    Note: This function is NOT safe for concurrent use. If two requests call
    this function simultaneously before either commits, they may receive the
    same position value. Callers should either:
    1. Use database-level locking (SELECT FOR UPDATE) around position assignment
    2. Handle unique constraint violations with retry logic
    3. Accept that position values may have gaps or duplicates

    For critical ordering requirements, consider using database sequences
    or adding a unique constraint on (user_id, parent_id, position).

    Args:
        db: Database session
        model: SQLAlchemy model class (must have position and user_id columns)
        user_id: User ID for scoping
        parent_id: Optional parent ID for hierarchical models (e.g., subtasks).
                   If the model has parent_id and this is None, filters for
                   root-level items (parent_id IS NULL).
        check_deleted: Whether to exclude soft-deleted records (default True)
        extra_filters: Optional list of additional SQLAlchemy filter conditions

    Returns:
        Next position value (1 if no existing records)

    Example:
        # Get next position for root-level todos
        position = await get_next_position(db, Todo, user.id)

        # Get next position for subtasks under a parent
        position = await get_next_position(db, Todo, user.id, parent_id=parent.id)

        # Get next position for projects (no parent_id)
        position = await get_next_position(db, Project, user.id)
    """
    query = select(sql_func.max(model.position)).where(model.user_id == user_id)

    # Handle parent_id filtering for hierarchical models
    if hasattr(model, "parent_id"):
        if parent_id is not None:
            query = query.where(model.parent_id == parent_id)
        else:
            query = query.where(model.parent_id.is_(None))

    # Filter out soft-deleted records
    if check_deleted and hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    # Apply any additional filters
    if extra_filters:
        for condition in extra_filters:
            query = query.where(condition)

    result = await db.execute(query)
    max_pos = result.scalar() or 0
    return max_pos + 1


async def verify_resource_exists(
    db: AsyncSession,
    model: Any,
    resource_id: int,
    user_id: int,
    error_factory: Callable[[], ApiError],
    *,
    check_deleted: bool = True,
) -> Any:
    """Verify a resource exists and belongs to the user.

    Alias for get_resource_for_user with clearer intent for validation-only cases.
    Use when you need to verify a resource exists (e.g., parent todo, project)
    but don't necessarily need to use all its data.

    Args:
        db: Database session
        model: SQLAlchemy model class
        resource_id: Resource ID to verify
        user_id: User ID for authorization check
        error_factory: Error factory function
        check_deleted: Whether to filter by deleted_at (default True)

    Returns:
        Model instance (for cases where you do need the data)

    Raises:
        ApiError: From error_factory if resource not found

    Example:
        # Verify project exists before creating a todo
        if request.project_id:
            await verify_resource_exists(
                db, Project, request.project_id, user.id, errors.project_not_found
            )
    """
    return await get_resource_for_user(
        db, model, resource_id, user_id, error_factory, check_deleted=check_deleted
    )


async def get_project_info(
    db: AsyncSession,
    project_id: int | None,
    user_id: int,
) -> tuple[str | None, str | None]:
    """Get project name and color, with authorization check.

    Args:
        db: Database session
        project_id: Project ID (returns (None, None) if None)
        user_id: User ID for authorization check

    Returns:
        Tuple of (project_name, project_color), or (None, None) if no project
    """
    if not project_id:
        return None, None
    result = await db.execute(
        select(Project.name, Project.color).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    row = result.one_or_none()
    return (row.name, row.color) if row else (None, None)


async def get_resources_for_user(
    db: AsyncSession,
    model: Any,
    resource_ids: list[int],
    user_id: int,
    *,
    check_deleted: bool = True,
) -> dict[int, Any]:
    """Get multiple resources by IDs, ensuring they belong to the user.

    Useful for bulk operations where you need to verify ownership of
    multiple resources at once.

    Args:
        db: Database session
        model: SQLAlchemy model class
        resource_ids: List of resource IDs to fetch
        user_id: User ID for authorization check
        check_deleted: Whether to filter by deleted_at (default True)

    Returns:
        Dictionary mapping resource ID to model instance.
        Only includes resources that exist and belong to the user.

    Example:
        todos = await get_resources_for_user(db, Todo, [1, 2, 3], user.id)
        missing_ids = set(request_ids) - set(todos.keys())
        if missing_ids:
            raise errors.not_found(f"Todos not found: {missing_ids}")
    """
    query = select(model).where(
        model.id.in_(resource_ids),
        model.user_id == user_id,
    )
    if check_deleted and hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))

    result = await db.execute(query)
    resources = result.scalars().all()
    return {r.id: r for r in resources}
