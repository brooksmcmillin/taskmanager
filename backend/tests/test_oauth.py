"""Tests for OAuth endpoints."""

import pytest
from httpx import AsyncClient


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
