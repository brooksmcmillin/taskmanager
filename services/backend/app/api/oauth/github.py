"""GitHub OAuth endpoints for social login."""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.config import settings
from app.core.errors import errors
from app.core.security import generate_session_id, get_session_expiry, hash_password
from app.dependencies import CurrentUser, DbSession
from app.models.oauth_provider import UserOAuthProvider
from app.models.session import Session
from app.models.user import User
from app.services.github_oauth import (
    GitHubOAuthError,
    exchange_code_for_token,
    generate_state,
    get_authorization_url,
    get_user_info,
    is_github_configured,
)

router = APIRouter(prefix="/api/auth/github", tags=["github-oauth"])

# In-memory state storage (in production, use Redis or database)
# Maps state -> {return_to: str, created_at: datetime}
_oauth_states: dict[str, dict] = {}


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
    return_to: str = Query("/", description="URL to redirect after authentication"),
) -> RedirectResponse:
    """Start GitHub OAuth flow by redirecting to GitHub.

    Args:
        return_to: URL to redirect to after successful authentication
    """
    if not is_github_configured():
        raise errors.github_not_configured()

    # Generate and store state
    state = generate_state()
    _oauth_states[state] = {"return_to": return_to}

    # Redirect to GitHub
    auth_url = get_authorization_url(state)
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/callback")
async def github_callback(
    request: Request,
    response: Response,
    db: DbSession,
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: str | None = Query(None, description="Error from GitHub"),
    error_description: str | None = Query(None, description="Error description"),
) -> RedirectResponse:
    """Handle GitHub OAuth callback.

    This endpoint:
    1. Validates the state parameter
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

    # Validate state
    state_data = _oauth_states.pop(state, None)
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
            existing_provider.access_token = access_token
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
                    access_token=access_token,
                )
                db.add(oauth_provider)
            else:
                # Create new user
                # Generate a unique username based on GitHub username
                username = await _generate_unique_username(db, github_user.login)

                # Generate a random password (user can set one later if they want)
                random_password = secrets.token_urlsafe(32)

                user = User(
                    username=username,
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
                    access_token=access_token,
                )
                db.add(oauth_provider)

        # Create session
        session = Session(
            id=generate_session_id(),
            user_id=user.id,
            expires_at=get_session_expiry(),
        )
        db.add(session)

        # Redirect to frontend with session cookie
        redirect_response = RedirectResponse(url=return_to, status_code=302)
        redirect_response.set_cookie(
            key="session",
            value=session.id,
            httponly=True,
            samesite="lax",
            max_age=settings.session_duration_days * 24 * 60 * 60,
            secure=settings.is_production,
        )
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


async def _generate_unique_username(db: DbSession, base_username: str) -> str:
    """Generate a unique username based on the GitHub username.

    If the username is taken, append a number until we find a unique one.
    """
    # Clean the username (GitHub usernames are already pretty clean)
    username = base_username.lower()

    # Check if it's available
    result = await db.execute(select(User).where(User.username == username))
    if not result.scalar_one_or_none():
        return username

    # Try with numbers
    for i in range(1, 1000):
        candidate = f"{username}{i}"
        result = await db.execute(select(User).where(User.username == candidate))
        if not result.scalar_one_or_none():
            return candidate

    # Fallback to random suffix
    return f"{username}_{secrets.token_hex(4)}"


def _redirect_with_error(error_message: str) -> RedirectResponse:
    """Redirect to frontend login page with an error message."""
    params = urlencode({"error": error_message})
    return RedirectResponse(
        url=f"{settings.frontend_url}/login?{params}",
        status_code=302,
    )
