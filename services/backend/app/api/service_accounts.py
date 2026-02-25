"""Service account management endpoints for admin users."""

import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.errors import errors
from app.core.security import generate_token, hash_password
from app.dependencies import AdminUser, DbSession
from app.models.oauth import OAuthClient
from app.models.user import User

router = APIRouter(
    prefix="/api/admin/service-accounts",
    tags=["admin-service-accounts"],
)

# Unusable password marker following Django's convention: a prefix that can never
# be a valid bcrypt hash, making bcrypt.checkpw() always return False.
_LOCKED_PASSWORD_HASH = "!unusable_service_account_password"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ServiceAccountCreate(BaseModel):
    """Create service account request."""

    display_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    scopes: list[str] = Field(default=["read"])


class ServiceAccountUpdate(BaseModel):
    """Update service account request."""

    display_name: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    scopes: list[str] | None = None


class ServiceAccountResponse(BaseModel):
    """Service account response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str | None
    is_active: bool
    is_service_account: bool
    created_at: datetime
    oauth_client_id: str | None = None
    scopes: list[str] | None = None


class ServiceAccountCreateResponse(BaseModel):
    """Response returned when a service account is created.

    The client_secret is shown exactly once and cannot be retrieved later.
    """

    service_account: ServiceAccountResponse
    client_id: str
    client_secret: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_service_account(db: DbSession, account_id: int) -> User:
    """Fetch a service account by ID or raise 404.

    Looks up by ID first and checks is_service_account in application code so
    the query timing is identical regardless of whether the ID belongs to a
    regular user or a service account (avoids leaking valid user IDs).
    """
    result = await db.execute(select(User).where(User.id == account_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_service_account:
        raise errors.not_found("Service account")
    return user


async def _get_linked_client(db: DbSession, user_id: int) -> OAuthClient | None:
    """Get the OAuth client linked to a service account."""
    result = await db.execute(select(OAuthClient).where(OAuthClient.user_id == user_id))
    return result.scalar_one_or_none()


def _build_response(user: User, client: OAuthClient | None) -> ServiceAccountResponse:
    """Build a ServiceAccountResponse from a User and optional OAuthClient."""
    scopes = None
    client_id = None
    if client:
        client_id = client.client_id
        scopes = json.loads(client.scopes)
    return ServiceAccountResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_service_account=user.is_service_account,
        created_at=user.created_at,
        oauth_client_id=client_id,
        scopes=scopes,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_service_accounts(
    _admin: AdminUser,
    db: DbSession,
) -> dict:
    """List all service accounts."""
    result = await db.execute(
        select(User)
        .where(User.is_service_account.is_(True))
        .order_by(User.created_at.desc())
    )
    accounts = result.scalars().all()

    data = []
    for account in accounts:
        client = await _get_linked_client(db, account.id)
        data.append(_build_response(account, client))

    return {"data": data, "meta": {"count": len(data)}}


@router.post("", status_code=201)
async def create_service_account(
    request: ServiceAccountCreate,
    _admin: AdminUser,
    db: DbSession,
) -> dict:
    """Create a new service account with a linked OAuth client.

    Returns the client_id and client_secret. The secret is shown only once.
    """
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none():
        raise errors.email_exists()

    # Create the service account user
    user = User(
        email=request.email,
        password_hash=_LOCKED_PASSWORD_HASH,
        is_service_account=True,
        display_name=request.display_name,
    )
    db.add(user)
    await db.flush()  # get user.id

    # Create a linked OAuth client with client_credentials grant
    client_id = generate_token(16)
    client_secret = generate_token(32)
    client_secret_hash = hash_password(client_secret)

    client = OAuthClient(
        user_id=user.id,
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        name=f"service-account-{user.id}",
        redirect_uris=json.dumps([]),
        grant_types=json.dumps(["client_credentials"]),
        scopes=json.dumps(request.scopes),
        is_public=False,
    )
    db.add(client)
    await db.flush()
    await db.commit()

    response = _build_response(user, client)

    return {
        "data": ServiceAccountCreateResponse(
            service_account=response,
            client_id=client_id,
            client_secret=client_secret,
        )
    }


@router.get("/{account_id}")
async def get_service_account(
    account_id: int,
    _admin: AdminUser,
    db: DbSession,
) -> dict:
    """Get a service account by ID."""
    user = await _get_service_account(db, account_id)
    client = await _get_linked_client(db, user.id)
    return {"data": _build_response(user, client)}


@router.patch("/{account_id}")
async def update_service_account(
    account_id: int,
    request: ServiceAccountUpdate,
    _admin: AdminUser,
    db: DbSession,
) -> dict:
    """Update a service account's display name, active status, or scopes."""
    user = await _get_service_account(db, account_id)
    client = await _get_linked_client(db, user.id)

    update_data = request.model_dump(exclude_unset=True)

    # Apply user-level fields
    if "display_name" in update_data:
        user.display_name = update_data["display_name"]
    if "is_active" in update_data:
        user.is_active = update_data["is_active"]
        # Also deactivate/activate the linked OAuth client
        if client:
            client.is_active = update_data["is_active"]

    # Apply scope changes to the OAuth client
    if "scopes" in update_data and client:
        client.scopes = json.dumps(update_data["scopes"])

    return {"data": _build_response(user, client)}


@router.delete("/{account_id}")
async def deactivate_service_account(
    account_id: int,
    _admin: AdminUser,
    db: DbSession,
) -> dict:
    """Deactivate a service account (soft delete).

    Sets is_active=False on both the user and its linked OAuth client.
    """
    user = await _get_service_account(db, account_id)
    user.is_active = False

    client = await _get_linked_client(db, user.id)
    if client:
        client.is_active = False

    return {"data": {"deactivated": True, "id": account_id}}
