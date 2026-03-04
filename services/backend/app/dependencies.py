"""FastAPI dependency injection."""

import ipaddress
import secrets
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import errors
from app.core.rate_limit import api_key_rate_limiter
from app.core.security import hash_password, is_api_key, verify_password
from app.core.tab_id import tab_id_var
from app.db.database import async_session_maker
from app.models.api_key import ApiKey
from app.models.session import Session
from app.models.user import User


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session."""
    async with async_session_maker() as session:
        try:
            # Propagate the tab ID into a PG session variable so that
            # the notify_event() trigger can include it in payloads.
            tab_id = tab_id_var.get("")
            if tab_id:
                await session.execute(
                    text("SELECT set_config('app.tab_id', :val, true)"),
                    {"val": tab_id},
                )
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
    from app.models.oauth import AccessToken

    result = await db.execute(
        select(AccessToken)
        .where(AccessToken.token == token)  # SQL filter (OK for performance)
        .where(AccessToken.expires_at > datetime.now(UTC))
        .where(AccessToken.revoked.is_(False))
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
    # Extract and validate token
    token = await _extract_bearer_token(request)
    access_token = await _validate_access_token(db, token)

    # Client credentials grants don't have a user_id
    if not access_token.user_id:
        raise errors.auth_required()

    # Get user and verify they are still active
    result = await db.execute(select(User).where(User.id == access_token.user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise errors.auth_required()

    return user


CurrentUserOAuth = Annotated[User, Depends(get_current_user_oauth)]


async def validate_client_credentials_token(
    request: Request,
    db: DbSession,
) -> str:
    """Validate OAuth Bearer token from client credentials grant.

    Accepts both system-level tokens (user_id=None) and service account
    tokens (user_id set, linked user has is_service_account=True).
    Returns the client_id associated with the token.
    """
    # Extract and validate token
    token = await _extract_bearer_token(request)
    access_token = await _validate_access_token(db, token)

    if not access_token.client_id:
        raise errors.invalid_token()

    # Allow system-level tokens (no user) and service account tokens
    if access_token.user_id is not None:
        result = await db.execute(select(User).where(User.id == access_token.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active or not user.is_service_account:
            raise errors.auth_required()

    return access_token.client_id


ClientCredentialsToken = Annotated[str, Depends(validate_client_credentials_token)]


async def _validate_api_key(
    db: DbSession, key: str, client_ip: str | None = None
) -> ApiKey:
    """Validate an API key and return the ApiKey model.

    Args:
        db: Database session
        key: The full API key string (tm_...)
        client_ip: Client IP address for rate limiting

    Returns:
        ApiKey model instance

    Raises:
        HTTPException: If key is invalid, expired, revoked, or rate limited
    """
    # Rate limit by IP address to prevent brute force attacks
    rate_limit_key = client_ip or "unknown"
    await api_key_rate_limiter.check(rate_limit_key, db)

    # Extract prefix for efficient lookup
    prefix = key[:11]

    # Find API keys with matching prefix
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.key_prefix == prefix)
        .where(ApiKey.is_active.is_(True))
    )
    api_keys = result.scalars().all()

    # Always perform at least one bcrypt verification to prevent timing attacks
    # This ensures consistent response time regardless of whether prefix exists
    if not api_keys:
        # Dummy hash to maintain constant timing
        hash_password("dummy_timing_normalization_value")
        await api_key_rate_limiter.record(rate_limit_key, db)
        raise errors.invalid_token()

    # Check each candidate with bcrypt verification
    for api_key in api_keys:
        if verify_password(key, api_key.key_hash):
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.now(UTC):
                await api_key_rate_limiter.record(rate_limit_key, db)
                raise errors.invalid_token()

            # Update last_used_at and commit immediately
            api_key.last_used_at = datetime.now(UTC)
            await db.commit()

            # Reset rate limiter on successful auth
            await api_key_rate_limiter.reset(rate_limit_key, db)
            return api_key

    # Record failed attempt for rate limiting
    await api_key_rate_limiter.record(rate_limit_key, db)
    raise errors.invalid_token()


def _parse_ip(value: str) -> str | None:
    """Return value if it is a valid IPv4/IPv6 address string, else None."""
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        return None


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP from request, validating X-Forwarded-For.

    To prevent IP spoofing, we do not blindly trust the leftmost entry in the
    X-Forwarded-For header.  Instead we count how many proxies are trusted
    (TRUSTED_PROXY_COUNT) and pick the IP that many positions from the right of
    the header list.

    Example with trusted_proxy_count=1 and header "1.2.3.4, 10.0.0.1":
      - The rightmost entry (10.0.0.1) was added by our single trusted proxy.
      - The entry just to the left of it (1.2.3.4) is the real client IP.

    If the X-Forwarded-For chain is shorter than expected, or if the selected
    entry is not a valid IP address (e.g. a hostname or "unknown"), we fall back
    to request.client.host, which is the TCP-layer address that cannot be
    spoofed by the client.
    """
    trusted_proxy_count = settings.trusted_proxy_count

    # When no proxies are trusted, always use the direct TCP connection address.
    if trusted_proxy_count <= 0:
        if request.client:
            return request.client.host
        return None

    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        # Split the comma-separated IP list and strip whitespace.
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        # We expect at least trusted_proxy_count entries appended by our proxies.
        # The real client IP sits one position before those proxy entries.
        # Required minimum list length: trusted_proxy_count + 1 (the actual client).
        if len(ips) > trusted_proxy_count:
            candidate = ips[-(trusted_proxy_count + 1)]
            parsed = _parse_ip(candidate)
            if parsed is not None:
                return parsed
        # The header chain is shorter than expected or contains non-IP values —
        # fall through to the direct host address.

    # Fall back to the direct TCP-layer peer address.
    if request.client:
        return request.client.host
    return None


async def get_current_user_api_key(
    request: Request,
    db: DbSession,
) -> User:
    """Get current authenticated user from API key."""
    client_ip = _get_client_ip(request)

    # Check X-API-Key header
    api_key_header = request.headers.get("X-API-Key")
    if api_key_header and is_api_key(api_key_header):
        api_key = await _validate_api_key(db, api_key_header, client_ip)
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
            api_key = await _validate_api_key(db, token, client_ip)
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
    user = await get_current_user_flexible(request, db)
    if not user.is_admin:
        raise errors.permission_denied()
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
