"""OAuth client management API."""

import json
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.errors import errors
from app.core.security import generate_token, hash_password
from app.dependencies import ClientCredentialsToken, CurrentUserFlexible, DbSession
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
    user: CurrentUserFlexible,
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
        "data": [
            ClientResponse(
                id=c.id,
                client_id=c.client_id,
                name=c.name,
                redirect_uris=json.loads(c.redirect_uris),
                grant_types=json.loads(c.grant_types),
                scopes=json.loads(c.scopes),
                is_active=c.is_active,
                is_public=c.is_public,
                created_at=c.created_at,
            )
            for c in clients
        ],
        "meta": {"count": len(clients)},
    }


@router.get("/{client_id}/info")
async def get_client_info(
    client_id: str,
    _authenticated_client: ClientCredentialsToken,
    db: DbSession,
) -> dict:
    """
    Get OAuth client information by client_id.

    This endpoint is for machine-to-machine (M2M) services that need to look up
    OAuth client metadata. It requires authentication with a client credentials token.

    This endpoint does NOT check user ownership - any authenticated M2M service
    can look up any client's metadata (similar to OAuth discovery endpoints).
    """
    result = await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == client_id)
    )
    client = result.scalar_one_or_none()

    if not client:
        raise errors.oauth_client_not_found()

    return {
        "data": ClientResponse(
            id=client.id,
            client_id=client.client_id,
            name=client.name,
            redirect_uris=json.loads(client.redirect_uris),
            grant_types=json.loads(client.grant_types),
            scopes=json.loads(client.scopes),
            is_active=client.is_active,
            is_public=client.is_public,
            created_at=client.created_at,
        )
    }


@router.post("", status_code=201)
async def create_client(
    request: ClientCreate,
    user: CurrentUserFlexible,
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
        redirect_uris=json.dumps(request.redirect_uris),
        grant_types=json.dumps(request.grant_types),
        scopes=json.dumps(request.scopes),
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
    user: CurrentUserFlexible,
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
        # Serialize list fields to JSON
        if field in ("redirect_uris", "grant_types", "scopes") and isinstance(
            value, list
        ):
            value = json.dumps(value)
        setattr(client, field, value)

    return {
        "data": ClientResponse(
            id=client.id,
            client_id=client.client_id,
            name=client.name,
            redirect_uris=json.loads(client.redirect_uris),
            grant_types=json.loads(client.grant_types),
            scopes=json.loads(client.scopes),
            is_active=client.is_active,
            is_public=client.is_public,
            created_at=client.created_at,
        )
    }


@router.delete("/{client_id}")
async def delete_client(
    client_id: str,
    user: CurrentUserFlexible,
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
