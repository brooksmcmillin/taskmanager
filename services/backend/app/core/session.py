"""Session creation and cookie management helpers.

Centralizes session creation and cookie setting logic used across
authentication endpoints (login, WebAuthn, GitHub OAuth).
"""

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import generate_session_id, get_session_expiry
from app.models.session import Session


async def create_session_and_set_cookie(
    db: AsyncSession,
    response: Response,
    user_id: int,
) -> Session:
    """Create a new session for a user and set the session cookie.

    Args:
        db: Database session
        response: FastAPI response to set cookie on
        user_id: ID of the user to create session for

    Returns:
        The created Session object
    """
    session = Session(
        id=generate_session_id(),
        user_id=user_id,
        expires_at=get_session_expiry(),
    )
    db.add(session)

    set_session_cookie(response, session.id)

    return session


def set_session_cookie(response: Response, session_id: str) -> None:
    """Set session cookie on a response."""
    response.set_cookie(
        key="session",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_duration_days * 24 * 60 * 60,
        secure=settings.is_production,
    )
