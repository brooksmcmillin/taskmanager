"""FastAPI dependency injection."""

import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import errors
from app.core.security import is_api_key, verify_password
from app.db.database import async_session_maker
from app.models.api_key import ApiKey
from app.models.session import Session
from app.models.user import User


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
    from datetime import datetime

    from sqlalchemy import select

    session_id = request.cookies.get("session")
    if not session_id:
        raise errors.auth_required()

    # Query session with user
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .where(Session.expires_at > datetime.now(UTC))
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


# OAuth token validation helpers
async def _extract_bearer_token(request: Request) -> str:
    """Extract Bearer token from Authorization header.

    Args:
        request: FastAPI request object

    Returns:
        The Bearer token string

    Raises:
        HTTPException: If Authorization header is missing or invalid
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise errors.auth_required()
    return auth_header.replace("Bearer ", "")


async def _validate_access_token(db: DbSession, token: str):
    """Validate access token with constant-time comparison.

    Args:
        db: Database session
        token: Access token string

    Returns:
        AccessToken model instance

    Raises:
        HTTPException: If token is invalid or expired
    """
    from datetime import datetime

    from sqlalchemy import select

    from app.models.oauth import AccessToken

    result = await db.execute(
        select(AccessToken)
        .where(AccessToken.token == token)  # SQL filter (OK for performance)
        .where(AccessToken.expires_at > datetime.now(UTC))
    )
    access_token = result.scalar_one_or_none()

    # Add constant-time verification to prevent timing attacks
    if not access_token or not secrets.compare_digest(
        access_token.token.encode("utf-8"), token.encode("utf-8")
    ):
        raise errors.invalid_token()

    return access_token


async def get_current_user_oauth(
    request: Request,
    db: DbSession,
) -> User:
    """Get current authenticated user from OAuth Bearer token."""
    from sqlalchemy import select

    # Extract and validate token
    token = await _extract_bearer_token(request)
    access_token = await _validate_access_token(db, token)

    # Client credentials grants don't have a user_id
    if not access_token.user_id:
        raise errors.auth_required()

    # Get user
    result = await db.execute(select(User).where(User.id == access_token.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise errors.auth_required()

    return user


CurrentUserOAuth = Annotated[User, Depends(get_current_user_oauth)]


async def validate_client_credentials_token(
    request: Request,
    db: DbSession,
) -> str:
    """Validate OAuth Bearer token from client credentials grant.

    This validates machine-to-machine tokens that don't have a user_id.
    Returns the client_id associated with the token.
    """
    # Extract and validate token
    token = await _extract_bearer_token(request)
    access_token = await _validate_access_token(db, token)

    # Client credentials grants have client_id but no user_id
    if access_token.user_id is not None:
        raise errors.auth_required()

    if not access_token.client_id:
        raise errors.invalid_token()

    return access_token.client_id


ClientCredentialsToken = Annotated[str, Depends(validate_client_credentials_token)]


async def _validate_api_key(db: DbSession, key: str) -> ApiKey:
    """Validate an API key and return the ApiKey model.

    Args:
        db: Database session
        key: The full API key string (tm_...)

    Returns:
        ApiKey model instance

    Raises:
        HTTPException: If key is invalid, expired, or revoked
    """
    # Extract prefix for efficient lookup
    prefix = key[:11]

    # Find API keys with matching prefix
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.key_prefix == prefix)
        .where(ApiKey.is_active.is_(True))
    )
    api_keys = result.scalars().all()

    # Check each candidate with constant-time comparison
    for api_key in api_keys:
        if verify_password(key, api_key.key_hash):
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
                raise errors.invalid_token()

            # Update last_used_at
            api_key.last_used_at = datetime.now(UTC)
            return api_key

    raise errors.invalid_token()


async def get_current_user_api_key(
    request: Request,
    db: DbSession,
) -> User:
    """Get current authenticated user from API key."""
    # Check X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and is_api_key(api_key_header):
        api_key = await _validate_api_key(db, api_key_header)
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise errors.auth_required()
        return user

    # Check Authorization: Bearer header for API key
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        if is_api_key(token):
            api_key = await _validate_api_key(db, token)
            result = await db.execute(select(User).where(User.id == api_key.user_id))
            user = result.scalar_one_or_none()
            if not user:
                raise errors.auth_required()
            return user

    raise errors.auth_required()


CurrentUserApiKey = Annotated[User, Depends(get_current_user_api_key)]


async def get_current_user_flexible(
    request: Request,
    db: DbSession,
) -> User:
    """Get current user from session cookie, OAuth Bearer token, or API key."""
    # Check X-API-Key header first
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and is_api_key(api_key_header):
        return await get_current_user_api_key(request, db)

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        # Check if it's an API key
        if is_api_key(token):
            return await get_current_user_api_key(request, db)
        # Otherwise treat as OAuth token
        return await get_current_user_oauth(request, db)

    # Fall back to session cookie
    return await get_current_user(request, db)


CurrentUserFlexible = Annotated[User, Depends(get_current_user_flexible)]


async def get_admin_user(
    request: Request,
    db: DbSession,
) -> User:
    """Get current authenticated admin user."""
    user = await get_current_user(request, db)
    if not user.is_admin:
        raise errors.permission_denied()
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
