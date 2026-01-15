"""FastAPI dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.core.errors import errors
from app.models.user import User
from app.models.session import Session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DbSession,
) -> User:
    """Get current authenticated user from session cookie."""
    from sqlalchemy import select
    from datetime import datetime, timezone

    session_id = request.cookies.get("session")
    if not session_id:
        raise errors.auth_required()

    # Query session with user
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .where(Session.expires_at > datetime.now(timezone.utc))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise errors.session_expired()

    # Get user
    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise errors.auth_required()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    request: Request,
    db: DbSession,
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
