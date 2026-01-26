"""Registration code management API."""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import errors
from app.dependencies import AdminUser, DbSession
from app.models.registration_code import RegistrationCode

router = APIRouter(prefix="/api/registration-codes", tags=["registration-codes"])


# Schemas
class RegistrationCodeCreate(BaseModel):
    """Create registration code request."""

    code: str | None = Field(
        default=None,
        min_length=4,
        max_length=64,
        description="Custom code or leave empty to auto-generate",
    )
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_at: datetime | None = None


class RegistrationCodeResponse(BaseModel):
    """Registration code response."""

    id: int
    code: str
    max_uses: int
    current_uses: int
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    created_by_username: str | None = None

    class Config:
        from_attributes = True


class RegistrationCodeListResponse(BaseModel):
    """List of registration codes."""

    data: list[RegistrationCodeResponse]
    meta: dict


@router.get("")
async def list_registration_codes(
    admin: AdminUser,
    db: DbSession,
) -> RegistrationCodeListResponse:
    """List all registration codes (admin only)."""
    from app.models.user import User

    result = await db.execute(
        select(RegistrationCode, User.username)
        .outerjoin(User, RegistrationCode.created_by_id == User.id)
        .order_by(RegistrationCode.created_at.desc())
    )
    rows = result.all()

    codes = [
        RegistrationCodeResponse(
            id=code.id,
            code=code.code,
            max_uses=code.max_uses,
            current_uses=code.current_uses,
            is_active=code.is_active,
            expires_at=code.expires_at,
            created_at=code.created_at,
            created_by_username=username,
        )
        for code, username in rows
    ]

    return RegistrationCodeListResponse(
        data=codes,
        meta={"count": len(codes)},
    )


@router.post("", status_code=201)
async def create_registration_code(
    request: RegistrationCodeCreate,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Create a new registration code (admin only)."""
    # Generate code if not provided
    code_value = request.code or secrets.token_urlsafe(16)

    # Check if code already exists
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.code == code_value)
    )
    if result.scalar_one_or_none():
        raise errors.registration_code_exists()

    registration_code = RegistrationCode(
        code=code_value,
        max_uses=request.max_uses,
        expires_at=request.expires_at,
        created_by_id=admin.id,
    )
    db.add(registration_code)
    await db.flush()

    return {
        "data": RegistrationCodeResponse(
            id=registration_code.id,
            code=registration_code.code,
            max_uses=registration_code.max_uses,
            current_uses=registration_code.current_uses,
            is_active=registration_code.is_active,
            expires_at=registration_code.expires_at,
            created_at=registration_code.created_at,
            created_by_username=admin.username,
        )
    }


@router.delete("/{code_id}")
async def delete_registration_code(
    code_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Delete a registration code (admin only)."""
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.id == code_id)
    )
    registration_code = result.scalar_one_or_none()

    if not registration_code:
        raise errors.registration_code_not_found()

    await db.delete(registration_code)

    return {"data": {"deleted": True, "id": code_id}}


@router.patch("/{code_id}/deactivate")
async def deactivate_registration_code(
    code_id: int,
    admin: AdminUser,
    db: DbSession,
) -> dict:
    """Deactivate a registration code (admin only)."""
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.id == code_id)
    )
    registration_code = result.scalar_one_or_none()

    if not registration_code:
        raise errors.registration_code_not_found()

    registration_code.is_active = False

    return {
        "data": RegistrationCodeResponse(
            id=registration_code.id,
            code=registration_code.code,
            max_uses=registration_code.max_uses,
            current_uses=registration_code.current_uses,
            is_active=registration_code.is_active,
            expires_at=registration_code.expires_at,
            created_at=registration_code.created_at,
        )
    }


async def validate_and_use_registration_code(db: DbSession, code: str) -> None:
    """Atomically validate and increment registration code usage.

    Uses SELECT FOR UPDATE to prevent race conditions where multiple
    concurrent registrations could use the same code beyond max_uses.
    """
    # Lock the row for update to prevent race conditions
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.code == code).with_for_update()
    )
    registration_code = result.scalar_one_or_none()

    # Validate the code
    if not registration_code:
        raise errors.invalid_registration_code()

    if not registration_code.is_active:
        raise errors.invalid_registration_code()

    if registration_code.current_uses >= registration_code.max_uses:
        raise errors.registration_code_exhausted()

    if registration_code.expires_at and registration_code.expires_at < datetime.now(
        UTC
    ):
        raise errors.invalid_registration_code()

    # Atomically increment usage count while row is locked
    registration_code.current_uses += 1


async def validate_registration_code(db: DbSession, code: str) -> RegistrationCode:
    """Validate and return a registration code, or raise an error.

    WARNING: This function is NOT race-condition safe for registration.
    Use validate_and_use_registration_code() instead for registration flows.
    This function is kept for read-only validation purposes only.
    """
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.code == code)
    )
    registration_code = result.scalar_one_or_none()

    if not registration_code:
        raise errors.invalid_registration_code()

    if not registration_code.is_active:
        raise errors.invalid_registration_code()

    if registration_code.current_uses >= registration_code.max_uses:
        raise errors.registration_code_exhausted()

    if registration_code.expires_at and registration_code.expires_at < datetime.now(
        UTC
    ):
        raise errors.invalid_registration_code()

    return registration_code


async def use_registration_code(db: DbSession, code: str) -> None:
    """Increment the use count for a registration code.

    WARNING: This function is NOT race-condition safe when used separately
    from validate_registration_code(). Use validate_and_use_registration_code()
    instead for atomic validation and usage.
    """
    result = await db.execute(
        select(RegistrationCode).where(RegistrationCode.code == code)
    )
    registration_code = result.scalar_one_or_none()

    if registration_code:
        registration_code.current_uses += 1
