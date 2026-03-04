"""GitHub OAuth endpoints for social login."""

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import errors
from app.core.security import hash_password
from app.core.session import create_session_and_set_cookie
from app.dependencies import CurrentUser, DbSession
from app.models.oauth_provider import UserOAuthProvider
from app.models.shared_state import SharedState
from app.models.user import User
from app.services.github_oauth import (
    GitHubOAuthError,
    exchange_code_for_token,
    generate_state,
    get_authorization_url,
    get_user_info,
    is_github_configured,
)
from app.services.token_encryption import encrypt_token

router = APIRouter(prefix="/api/auth/github", tags=["github-oauth"])

OAUTH_STATE_NAMESPACE = "oauth_state"
STATE_EXPIRY_MINUTES = 5


class GitHubConfigResponse(BaseModel):
    """Response for GitHub OAuth configuration status."""

    enabled: bool
    authorize_url: str | None = None


class OAuthProviderResponse(BaseModel):
    """Response for a connected OAuth provider."""

    provider: str
    provider_username: str | None
    provider_email: str | None
    avatar_url: str | None
    connected_at: str


async def _cleanup_expired_states(db: AsyncSession) -> None:
    """Remove expired OAuth states from the database."""
    now = datetime.now(UTC)
    await db.execute(
        delete(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.expires_at <= now,
        )
    )


async def _store_oauth_state(db: AsyncSession, state: str, return_to: str) -> None:
    """Store an OAuth state token in the database with TTL."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=STATE_EXPIRY_MINUTES)

    entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key=state,
        value={"return_to": return_to},
        expires_at=expires_at,
    )
    db.add(entry)
    # Flush to ensure the state is written before we redirect
    await db.flush()


async def _validate_and_consume_state(state: str, db: AsyncSession) -> dict | None:
    """Validate state parameter and remove it from storage.

    Returns the state data if valid, None if invalid or expired.
    """
    now = datetime.now(UTC)

    # Look up and delete in one operation
    result = await db.execute(
        select(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.key == state,
        )
    )
    entry = result.scalar_one_or_none()

    if not entry:
        return None

    # Remove the state (consume it)
    await db.delete(entry)
    await db.flush()

    # Check expiration
    if entry.expires_at < now:
        return None

    return entry.value


def _validate_return_to(return_to: str) -> str:
    """Validate return_to is a safe local URL.

    Only allows relative URLs (no scheme/domain) to prevent open redirect attacks.
    """
    if not return_to:
        return "/"

    # Parse the URL
    parsed = urlparse(return_to)

    # Reject URLs with scheme or netloc (domain)
    if parsed.scheme or parsed.netloc:
        return "/"

    # Prevent protocol-relative URLs (//evil.com)
    if return_to.startswith("//"):
        return "/"

    # Ensure it starts with /
    if not return_to.startswith("/"):
        return "/"

    return return_to


@router.get("/config")
async def get_github_config() -> GitHubConfigResponse:
    """Check if GitHub OAuth is configured and return the authorize URL if so."""
    if not is_github_configured():
        return GitHubConfigResponse(enabled=False)

    return GitHubConfigResponse(
        enabled=True,
        authorize_url="/api/auth/github/authorize",
    )


@router.get("/authorize")
async def github_authorize(
    db: DbSession,
    return_to: str = Query("/", description="URL to redirect after authentication"),
) -> RedirectResponse:
    """Start GitHub OAuth flow by redirecting to GitHub.

    Args:
        db: Database session for storing OAuth state.
        return_to: URL to redirect to after successful authentication (must be relative)
    """
    if not is_github_configured():
        raise errors.github_not_configured()

    # Validate return_to to prevent open redirect
    safe_return_to = _validate_return_to(return_to)

    # Generate and store state in database
    state = generate_state()
    await _store_oauth_state(db, state, safe_return_to)

    # Redirect to GitHub
    auth_url = get_authorization_url(state)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback")
async def github_callback(
    request: Request,
    response: Response,
    db: DbSession,
    code: str | None = Query(None, description="Authorization code from GitHub"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: str | None = Query(None, description="Error from GitHub"),
    error_description: str | None = Query(None, description="Error description"),
) -> RedirectResponse:
    """Handle GitHub OAuth callback.

    This endpoint:
    1. Validates the state parameter (with expiration check)
    2. Exchanges the code for an access token
    3. Fetches user info from GitHub
    4. Creates or links the user account
    5. Creates a session and redirects to the frontend
    """
    if not is_github_configured():
        raise errors.github_not_configured()

    # Check for errors from GitHub
    if error:
        error_msg = error_description or error
        return _redirect_with_error(error_msg)

    # Validate that code is present (required when no error)
    if not code:
        return _redirect_with_error("Missing authorization code")

    # Validate and consume state (checks expiration)
    state_data = await _validate_and_consume_state(state, db)
    if not state_data:
        return _redirect_with_error("Invalid or expired OAuth state")

    return_to = state_data.get("return_to", "/")

    try:
        # Exchange code for token
        access_token = await exchange_code_for_token(code)

        # Get user info from GitHub
        github_user = await get_user_info(access_token)

        if not github_user.email:
            return _redirect_with_error(
                "Your GitHub account must have a verified email address"
            )

        # Encrypt the access token before storing
        encrypted_token = encrypt_token(access_token)

        # Check if this GitHub account is already linked to a user
        result = await db.execute(
            select(UserOAuthProvider).where(
                UserOAuthProvider.provider == "github",
                UserOAuthProvider.provider_user_id == github_user.id,
            )
        )
        existing_provider = result.scalar_one_or_none()

        if existing_provider:
            # User already linked - log them in
            user = existing_provider.user

            # Update provider info in case it changed
            existing_provider.provider_username = github_user.login
            existing_provider.provider_email = github_user.email
            existing_provider.avatar_url = github_user.avatar_url
            existing_provider.access_token = encrypted_token
        else:
            # Check if a user with this email already exists
            result = await db.execute(
                select(User).where(User.email == github_user.email)
            )
            user = result.scalar_one_or_none()

            if user:
                # Link GitHub to existing user
                oauth_provider = UserOAuthProvider(
                    user_id=user.id,
                    provider="github",
                    provider_user_id=github_user.id,
                    provider_username=github_user.login,
                    provider_email=github_user.email,
                    avatar_url=github_user.avatar_url,
                    access_token=encrypted_token,
                )
                db.add(oauth_provider)
            else:
                # Create new user
                # Generate a random password (user can set one later if they want)
                random_password = secrets.token_urlsafe(32)

                user = User(
                    email=github_user.email,
                    password_hash=hash_password(random_password),
                )
                db.add(user)
                await db.flush()  # Get user ID

                # Create OAuth provider link
                oauth_provider = UserOAuthProvider(
                    user_id=user.id,
                    provider="github",
                    provider_user_id=github_user.id,
                    provider_username=github_user.login,
                    provider_email=github_user.email,
                    avatar_url=github_user.avatar_url,
                    access_token=encrypted_token,
                )
                db.add(oauth_provider)

        # Create session and redirect with cookie
        redirect_response = RedirectResponse(url=return_to, status_code=302)
        await create_session_and_set_cookie(db, redirect_response, user.id)
        return redirect_response

    except GitHubOAuthError as e:
        return _redirect_with_error(e.message)


@router.get("/providers")
async def get_connected_providers(
    user: CurrentUser,
    db: DbSession,
) -> list[OAuthProviderResponse]:
    """Get list of OAuth providers connected to the current user's account."""
    result = await db.execute(
        select(UserOAuthProvider).where(UserOAuthProvider.user_id == user.id)
    )
    providers = result.scalars().all()

    return [
        OAuthProviderResponse(
            provider=p.provider,
            provider_username=p.provider_username,
            provider_email=p.provider_email,
            avatar_url=p.avatar_url,
            connected_at=p.created_at.isoformat(),
        )
        for p in providers
    ]


@router.delete("/disconnect")
async def disconnect_github(
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Disconnect GitHub from the current user's account."""
    result = await db.execute(
        select(UserOAuthProvider).where(
            UserOAuthProvider.user_id == user.id,
            UserOAuthProvider.provider == "github",
        )
    )
    provider = result.scalar_one_or_none()

    if not provider:
        raise errors.not_found("GitHub connection")

    await db.delete(provider)

    return {"message": "GitHub disconnected successfully"}


def _redirect_with_error(error_message: str) -> RedirectResponse:
    """Redirect to frontend login page with an error message."""
    params = urlencode({"error": error_message})
    return RedirectResponse(
        url=f"{settings.frontend_url}/login?{params}",
        status_code=302,
    )
