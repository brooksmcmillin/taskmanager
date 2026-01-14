"""OAuth client management API."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.dependencies import DbSession, CurrentUser
from app.core.errors import errors
from app.core.security import generate_token, hash_password
from app.models.oauth import OAuthClient

router = APIRouter(prefix="/api/oauth/clients", tags=["oauth"])


# Schemas
class ClientCreate(BaseModel):
    """Create OAuth client request."""

    name: str = Field(..., min_length=1, max_length=100)
    redirect_uris: list[str] = Field(alias="redirectUris")
    grant_types: list[str] = Field(
        default=["authorization_code", "refresh_token"],
        alias="grantTypes",
    )
    scopes: list[str] = Field(default=["read", "write"])
    is_public: bool = Field(default=False, alias="isPublic")
    client_secret: str | None = Field(default=None, alias="clientSecret")

    class Config:
        populate_by_name = True


class ClientUpdate(BaseModel):
    """Update OAuth client request."""

    name: str | None = None
    redirect_uris: list[str] | None = Field(default=None, alias="redirectUris")
    grant_types: list[str] | None = Field(default=None, alias="grantTypes")
    scopes: list[str] | None = None
    is_active: bool | None = Field(default=None, alias="isActive")

    class Config:
        populate_by_name = True


class ClientResponse(BaseModel):
    """OAuth client response."""

    id: int
    client_id: str
    name: str
    redirect_uris: list[str]
    grant_types: list[str]
    scopes: list[str]
    is_active: bool
    is_public: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ClientCreateResponse(BaseModel):
    """Response for client creation (includes secret)."""

    client_id: str
    client_secret: str | None
    name: str


@router.get("")
async def list_clients(
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """List OAuth clients for the user."""
    result = await db.execute(
        select(OAuthClient)
        .where(OAuthClient.user_id == user.id)
        .order_by(OAuthClient.created_at.desc())
    )
    clients = result.scalars().all()

    return {
        "data": [ClientResponse.model_validate(c) for c in clients],
        "meta": {"count": len(clients)},
    }


@router.post("", status_code=201)
async def create_client(
    request: ClientCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new OAuth client."""
    client_id = generate_token(16)

    # Generate or use provided secret
    if request.is_public:
        client_secret = None
        client_secret_hash = None
    else:
        client_secret = request.client_secret or generate_token(32)
        client_secret_hash = hash_password(client_secret)

    client = OAuthClient(
        user_id=user.id,
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        name=request.name,
        redirect_uris=request.redirect_uris,
        grant_types=request.grant_types,
        scopes=request.scopes,
        is_public=request.is_public,
    )
    db.add(client)
    await db.flush()

    return {
        "data": ClientCreateResponse(
            client_id=client_id,
            client_secret=client_secret,
            name=request.name,
        )
    }


@router.put("/{client_id}")
async def update_client(
    client_id: str,
    request: ClientUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update an OAuth client."""
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.user_id == user.id,
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        raise errors.oauth_client_not_found()

    update_data = request.model_dump(exclude_unset=True, by_alias=False)
    for field, value in update_data.items():
        setattr(client, field, value)

    return {"data": ClientResponse.model_validate(client)}


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Delete an OAuth client."""
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.user_id == user.id,
        )
    )
    client = result.scalar_one_or_none()

    if not client:
        raise errors.oauth_client_not_found()

    await db.delete(client)

    return {"data": {"deleted": True}}
