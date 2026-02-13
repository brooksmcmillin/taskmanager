"""Authentication API routes."""

from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import delete, select

from app.config import settings
from app.core.errors import errors
from app.core.rate_limit import RateLimiter, login_rate_limiter
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

# Rate limiter for account modifications (5 attempts per 5 minutes)
account_update_rate_limiter = RateLimiter(max_attempts=5, window_ms=300000)


# Request/Response schemas
class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    registration_code: str | None = Field(None, min_length=1)

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

    email: str
    password: str


class UserResponse(BaseModel):
    """User data in response."""

    id: int
    email: str
    is_admin: bool = False


class AuthResponse(BaseModel):
    """Authentication response."""

    message: str
    user: UserResponse


class UpdateEmailRequest(BaseModel):
    """Update email request."""

    email: EmailStr


class UpdatePasswordRequest(BaseModel):
    """Update password request."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError(
                "Password must contain at least 2 of: "
                "lowercase, uppercase, numbers, special chars"
            )
        return v


@router.post("/register", status_code=201)
async def register(request: RegisterRequest, db: DbSession) -> AuthResponse:
    """Register a new user."""
    from app.api.registration_codes import validate_and_use_registration_code

    # Atomically validate and use registration code if required
    # IMPORTANT: This MUST happen first before email check to:
    # 1. Prevent race conditions via SELECT FOR UPDATE row locking
    # 2. Prevent using registration codes to enumerate existing accounts
    # Note: If email check fails after this, the code usage is still
    # incremented. This is intentional to prevent enumeration attacks.
    if settings.registration_code_required:
        if not request.registration_code:
            raise errors.validation("Registration code is required")
        # Lock the registration code row and atomically check + increment usage
        await validate_and_use_registration_code(db, request.registration_code)

    # Check if email exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise errors.email_exists()

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    await db.flush()

    return AuthResponse(
        message="Registration successful",
        user=UserResponse(id=user.id, email=user.email, is_admin=user.is_admin),
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

    email: str
    password: str
    return_to: str | None

    if "application/json" in content_type:
        # JSON request
        body = await request.json()
        email = str(body.get("email", ""))
        password = str(body.get("password", ""))
        return_to = None
    elif (
        "application/x-www-form-urlencoded" in content_type
        or "multipart/form-data" in content_type
    ):
        # Form request
        form = await request.form()
        email = str(form.get("email", ""))
        password = str(form.get("password", ""))
        return_to_val = form.get("return_to")
        return_to = str(return_to_val) if return_to_val else None
    else:
        raise errors.invalid_credentials()

    if not email or not password:
        raise errors.invalid_credentials()

    # Rate limiting by email
    login_rate_limiter.check(email)

    # Find user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        login_rate_limiter.record(email)
        raise errors.invalid_credentials()

    # Reset rate limit on success
    login_rate_limiter.reset(email)

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
        user=UserResponse(id=user.id, email=user.email, is_admin=user.is_admin),
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
            "email": user.email,
            "is_admin": user.is_admin,
        }
    }


@router.get("/me")
async def get_me(user: CurrentUser) -> dict:
    """Get current user information (alias for /session)."""
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
        }
    }


@router.put("/email")
async def update_email(
    request: UpdateEmailRequest,
    user: CurrentUser,
    db: DbSession,
) -> AuthResponse:
    """Update the current user's email address."""
    rate_limit_key = f"email_update_{user.id}"

    # Rate limit by user ID
    account_update_rate_limiter.check(rate_limit_key)

    # Check if email is already taken by another user
    # Always query to maintain constant-time response regardless of email existence
    result = await db.execute(
        select(User).where(User.email == request.email, User.id != user.id)
    )
    email_taken = result.scalar_one_or_none() is not None

    if email_taken:
        account_update_rate_limiter.record(rate_limit_key)
        raise errors.email_exists()

    # Reset rate limit on success
    account_update_rate_limiter.reset(rate_limit_key)

    # Update email
    user.email = request.email
    await db.flush()

    return AuthResponse(
        message="Email updated successfully",
        user=UserResponse(id=user.id, email=user.email, is_admin=user.is_admin),
    )


@router.put("/password")
async def update_password(
    request: UpdatePasswordRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Update the current user's password."""
    rate_limit_key = f"password_update_{user.id}"

    # Rate limit by user ID
    account_update_rate_limiter.check(rate_limit_key)

    # Verify current password
    if not verify_password(request.current_password, user.password_hash):
        account_update_rate_limiter.record(rate_limit_key)
        raise errors.invalid_credentials()

    # Reset rate limit on success
    account_update_rate_limiter.reset(rate_limit_key)

    # Update password
    user.password_hash = hash_password(request.new_password)

    # SECURITY: Invalidate all user sessions after password change
    # This ensures any compromised session tokens are revoked
    await db.execute(delete(Session).where(Session.user_id == user.id))

    await db.flush()

    return {"message": "Password updated successfully. Please log in again."}
