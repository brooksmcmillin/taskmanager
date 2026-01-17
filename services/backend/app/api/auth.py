"""Authentication API routes."""

import re
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, select

from app.config import settings
from app.core.errors import errors
from app.core.rate_limit import login_rate_limiter
from app.core.security import (
    generate_session_id,
    get_session_expiry,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.dependencies import CurrentUser, DbSession
from app.models.session import Session
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


# Request/Response schemas
class RegisterRequest(BaseModel):
    """User registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", v):
            raise ValueError("Username must start with a letter")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError(
                "Password must contain at least 2 of: "
                "lowercase, uppercase, numbers, special chars"
            )
        return v


class LoginRequest(BaseModel):
    """Login request."""

    username: str
    password: str


class UserResponse(BaseModel):
    """User data in response."""

    id: int
    username: str
    email: str


class AuthResponse(BaseModel):
    """Authentication response."""

    message: str
    user: UserResponse


@router.post("/register", status_code=201)
async def register(request: RegisterRequest, db: DbSession) -> AuthResponse:
    """Register a new user."""
    # Check if username exists
    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise errors.username_exists()

    # Check if email exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise errors.email_exists()

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    await db.flush()

    return AuthResponse(
        message="Registration successful",
        user=UserResponse(id=user.id, username=user.username, email=user.email),
    )


@router.post("/login", response_model=None)
async def login(
    request: Request,
    response: Response,
    db: DbSession,
):
    """Login and create session.

    Supports both JSON (for API clients) and form data (for OAuth flows).
    """
    # Determine content type and parse accordingly
    content_type = request.headers.get("content-type", "")

    username: str
    password: str
    return_to: str | None

    if "application/json" in content_type:
        # JSON request
        body = await request.json()
        username = str(body.get("username", ""))
        password = str(body.get("password", ""))
        return_to = None
    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        # Form request
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))
        return_to_val = form.get("return_to")
        return_to = str(return_to_val) if return_to_val else None
    else:
        raise errors.invalid_credentials()

    if not username or not password:
        raise errors.invalid_credentials()

    # Rate limiting by username
    login_rate_limiter.check(username)

    # Find user
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        login_rate_limiter.record(username)
        raise errors.invalid_credentials()

    # Reset rate limit on success
    login_rate_limiter.reset(username)

    # Create session
    session = Session(
        id=generate_session_id(),
        user_id=user.id,
        expires_at=get_session_expiry(),
    )
    db.add(session)

    # Set cookie
    response.set_cookie(
        key="session",
        value=session.id,
        httponly=True,
        samesite="lax",
        max_age=settings.session_duration_days * 24 * 60 * 60,
        secure=settings.is_production,
    )

    # For form submissions with return_to, redirect
    if return_to:
        # Validate return_to to prevent open redirect vulnerability
        parsed = urlparse(return_to)
        if parsed.scheme and not return_to.startswith(settings.frontend_url):
            raise errors.validation("Invalid redirect URL")

        redirect_response = RedirectResponse(url=return_to, status_code=302)
        # Copy the session cookie to the redirect response
        redirect_response.set_cookie(
            key="session",
            value=session.id,
            httponly=True,
            samesite="lax",
            max_age=settings.session_duration_days * 24 * 60 * 60,
            secure=settings.is_production,
        )
        return redirect_response

    # For JSON requests, return user info
    return AuthResponse(
        message="Login successful",
        user=UserResponse(id=user.id, username=user.username, email=user.email),
    )


@router.post("/logout")
async def logout(
    response: Response,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Logout and clear session."""
    # Delete user's sessions
    await db.execute(delete(Session).where(Session.user_id == user.id))

    # Clear cookie
    response.delete_cookie("session")

    return {"message": "Logged out successfully"}


@router.get("/session")
async def get_session(user: CurrentUser) -> dict:
    """Get current session user information."""
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
    }
