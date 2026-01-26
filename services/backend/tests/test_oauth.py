"""Tests for OAuth endpoints."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.oauth import DeviceCode


@pytest.mark.asyncio
async def test_list_clients_empty(authenticated_client: AsyncClient):
    """Test listing OAuth clients when none exist."""
    response = await authenticated_client.get("/api/oauth/clients")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_create_client(authenticated_client: AsyncClient):
    """Test creating an OAuth client."""
    response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Test Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["authorization_code", "refresh_token"],
            "scopes": ["read", "write"],
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test Client"
    assert "client_id" in data
    assert "client_secret" in data  # Confidential client


@pytest.mark.asyncio
async def test_create_public_client(authenticated_client: AsyncClient):
    """Test creating a public OAuth client."""
    response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Public Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "isPublic": True,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["client_secret"] is None


@pytest.mark.asyncio
async def test_device_code_flow(authenticated_client: AsyncClient):
    """Test device code authorization flow."""
    # First create a client that supports device_code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["device_code", "refresh_token"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    # Request device code
    response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read write"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "device_code" in data
    assert "user_code" in data
    assert "verification_uri" in data
    assert data["expires_in"] > 0
    assert data["interval"] > 0

    # User code format: XXXX-XXXX
    user_code = data["user_code"]
    assert len(user_code) == 9
    assert user_code[4] == "-"


@pytest.mark.asyncio
async def test_device_code_scope_serialization(authenticated_client: AsyncClient, db):
    """Test that device code scopes are properly serialized as JSON."""
    # Create a device code client
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    # Request device code with multiple scopes
    response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read write"},
    )
    assert response.status_code == 200
    device_code = response.json()["device_code"]

    # Verify scopes are stored as JSON in database
    result = await db.execute(
        select(DeviceCode).where(DeviceCode.device_code == device_code)
    )
    dc = result.scalar_one()

    # Scopes should be stored as JSON string
    assert isinstance(dc.scopes, str)
    scopes_list = json.loads(dc.scopes)
    assert scopes_list == ["read", "write"]


@pytest.mark.asyncio
async def test_device_lookup_endpoint(authenticated_client: AsyncClient):
    """Test device lookup endpoint returns correct details."""
    # Create client and device code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Test Device",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read"},
    )
    user_code = device_response.json()["user_code"]

    # Lookup device code
    response = await authenticated_client.get(
        f"/api/oauth/device/lookup?user_code={user_code}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_code"] == user_code
    assert data["client_id"] == client_id
    assert data["client_name"] == "Test Device"
    assert "scopes" in data
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_device_lookup_invalid_code(authenticated_client: AsyncClient):
    """Test device lookup with invalid code returns 404."""
    response = await authenticated_client.get(
        "/api/oauth/device/lookup?user_code=INVALID-CODE"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_device_lookup_requires_auth(client: AsyncClient):
    """Test device lookup requires authentication."""
    response = await client.get("/api/oauth/device/lookup?user_code=XXXX-YYYY")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_device_authorize_json(authenticated_client: AsyncClient):
    """Test device authorization with JSON payload."""
    # Create client and device code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read"},
    )
    user_code = device_response.json()["user_code"]

    # Authorize device with JSON
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={"user_code": user_code, "action": "allow"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert "message" in data


@pytest.mark.asyncio
async def test_device_authorize_deny(authenticated_client: AsyncClient):
    """Test denying device authorization."""
    # Create client and device code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read"},
    )
    user_code = device_response.json()["user_code"]

    # Deny device
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={"user_code": user_code, "action": "deny"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "denied"


@pytest.mark.asyncio
async def test_device_token_exchange(
    authenticated_client: AsyncClient, client: AsyncClient
):
    """Test full device code token exchange flow."""
    # Create client and device code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": [
                "urn:ietf:params:oauth:grant-type:device_code",
                "refresh_token",
            ],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read"},
    )
    device_code = device_response.json()["device_code"]
    user_code = device_response.json()["user_code"]

    # Try token exchange before authorization - should get authorization_pending
    token_response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        },
    )
    assert token_response.status_code == 400
    error_data = token_response.json()
    assert error_data["detail"]["code"] == "OAUTH_008"  # Authorization pending

    # Authorize device
    await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={"user_code": user_code, "action": "allow"},
    )

    # Try token exchange again - should succeed
    token_response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        },
    )
    assert token_response.status_code == 200
    token_data = token_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "Bearer"
    assert token_data["scope"] == "read"


@pytest.mark.asyncio
async def test_device_token_scope_deserialization(
    authenticated_client: AsyncClient, client: AsyncClient
):
    """Test that token response properly deserializes scopes from JSON."""
    # Create client with multiple scopes
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read write"},
    )
    device_code = device_response.json()["device_code"]
    user_code = device_response.json()["user_code"]

    # Authorize device
    await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={"user_code": user_code, "action": "allow"},
    )

    # Exchange for token
    token_response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        },
    )

    assert token_response.status_code == 200
    token_data = token_response.json()
    # Scope should be space-separated string, not JSON
    assert token_data["scope"] == "read write"
    assert " " in token_data["scope"]  # Not "[ " r e a d " ]"


@pytest.mark.asyncio
async def test_device_code_expiry_timezone_handling(
    authenticated_client: AsyncClient, client: AsyncClient, db
):
    """Test expired device codes with timezone-aware comparison."""
    # Create client and device code
    client_response = await authenticated_client.post(
        "/api/oauth/clients",
        json={
            "name": "Device Client",
            "redirectUris": ["http://localhost:3000/callback"],
            "grantTypes": ["urn:ietf:params:oauth:grant-type:device_code"],
            "isPublic": True,
        },
    )
    client_id = client_response.json()["data"]["client_id"]

    device_response = await authenticated_client.post(
        "/api/oauth/device/code",
        data={"client_id": client_id, "scope": "read"},
    )
    device_code = device_response.json()["device_code"]
    user_code = device_response.json()["user_code"]

    # Manually expire the device code
    result = await db.execute(
        select(DeviceCode).where(DeviceCode.device_code == device_code)
    )
    dc = result.scalar_one()
    dc.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()

    # Try to look up expired code
    lookup_response = await authenticated_client.get(
        f"/api/oauth/device/lookup?user_code={user_code}"
    )
    assert lookup_response.status_code == 404

    # Try to authorize expired code
    auth_response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={"user_code": user_code, "action": "allow"},
    )
    assert auth_response.status_code == 404


@pytest.mark.asyncio
async def test_auth_me_endpoint(authenticated_client: AsyncClient):
    """Test /api/auth/me endpoint returns user info."""
    response = await authenticated_client.get("/api/auth/me")

    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "id" in data["user"]
    assert "username" in data["user"]
    assert "email" in data["user"]


@pytest.mark.asyncio
async def test_auth_me_requires_authentication(client: AsyncClient):
    """Test /api/auth/me requires authentication."""
    response = await client.get("/api/auth/me")
    assert response.status_code == 401
