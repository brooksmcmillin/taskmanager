"""API Keys management endpoints."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import errors
from app.core.security import generate_api_key, get_api_key_prefix, hash_password
from app.dependencies import CurrentUser, DbSession
from app.models.api_key import ApiKey
from app.schemas import ListResponse

router = APIRouter(prefix="/api/api-keys", tags=["api-keys"])

MAX_API_KEYS_PER_USER = 10


# Schemas
# Note: scopes field removed - will be added back when scope enforcement is implemented


class ApiKeyCreate(BaseModel):
    """Create API key request."""

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: datetime | None = None


class ApiKeyUpdate(BaseModel):
    """Update API key request."""

    name: str | None = None
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    """API key response (without secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreateResponse(BaseModel):
    """API key creation response (includes secret once)."""

    id: int
    name: str
    key: str
    key_prefix: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime


def _to_response(api_key: ApiKey) -> ApiKeyResponse:
    """Convert ApiKey model to response schema."""
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
    )


@router.get("")
async def list_api_keys(
    user: CurrentUser,
    db: DbSession,
) -> ListResponse[ApiKeyResponse]:
    """List all API keys for the current user."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id)
        .order_by(ApiKey.created_at.desc())
    )
    api_keys = result.scalars().all()

    return ListResponse(
        data=[_to_response(k) for k in api_keys],
        meta={"count": len(api_keys)},
    )


@router.post("", status_code=201)
async def create_api_key(
    request: ApiKeyCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new API key.

    The secret key is only returned once and cannot be retrieved later.
    Store it securely.
    """
    # Check API key limit with row locking to prevent race condition
    # Select existing keys with FOR UPDATE to lock rows during the check
    existing_keys_result = await db.execute(
        select(ApiKey.id).where(ApiKey.user_id == user.id).with_for_update()
    )
    existing_keys = existing_keys_result.scalars().all()
    count = len(existing_keys)

    if count >= MAX_API_KEYS_PER_USER:
        raise errors.api_key_limit_exceeded(MAX_API_KEYS_PER_USER)

    # Generate the key
    secret_key = generate_api_key()
    key_hash = hash_password(secret_key)
    key_prefix = get_api_key_prefix(secret_key)

    api_key = ApiKey(
        user_id=user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=request.expires_at,
    )
    db.add(api_key)
    await db.flush()
    await db.commit()  # Explicit commit to ensure key is persisted

    return {
        "data": ApiKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            key=secret_key,
            key_prefix=key_prefix,
            is_active=api_key.is_active,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )
    }


@router.get("/{key_id}")
async def get_api_key(
    key_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get an API key by ID."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise errors.api_key_not_found()

    return {"data": _to_response(api_key)}


@router.put("/{key_id}")
async def update_api_key(
    key_id: int,
    request: ApiKeyUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update an API key's name or active status."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise errors.api_key_not_found()

    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(api_key, field, value)

    return {"data": _to_response(api_key)}


@router.delete("/{key_id}")
async def delete_api_key(
    key_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete an API key."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise errors.api_key_not_found()

    await db.delete(api_key)

    return {"data": {"deleted": True}}


@router.post("/{key_id}/revoke")
async def revoke_api_key(
    key_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Revoke (deactivate) an API key without deleting it."""
    result = await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user.id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise errors.api_key_not_found()

    api_key.is_active = False

    return {"data": _to_response(api_key)}
