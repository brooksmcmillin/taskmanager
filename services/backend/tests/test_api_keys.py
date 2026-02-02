"""Tests for API key authentication."""

import pytest
from httpx import AsyncClient

from app.core.security import generate_api_key, get_api_key_prefix


class TestApiKeyGeneration:
    """Test API key generation utilities."""

    def test_generate_api_key_format(self) -> None:
        """API key should have correct format."""
        key = generate_api_key()
        assert key.startswith("tm_")
        assert len(key) == 51  # 3 (prefix) + 48 (hex chars)

    def test_generate_api_key_unique(self) -> None:
        """Each generated key should be unique."""
        keys = [generate_api_key() for _ in range(100)]
        assert len(set(keys)) == 100

    def test_get_api_key_prefix(self) -> None:
        """Prefix should be first 11 chars."""
        key = generate_api_key()
        prefix = get_api_key_prefix(key)
        assert prefix == key[:11]
        assert len(prefix) == 11


class TestApiKeyCrud:
    """Test API key CRUD operations."""

    @pytest.mark.asyncio
    async def test_list_api_keys_unauthenticated(self, client: AsyncClient) -> None:
        """Listing API keys requires authentication."""
        response = await client.get("/api/api-keys")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_api_keys_empty(self, authenticated_client: AsyncClient) -> None:
        """Empty list when no API keys exist."""
        response = await authenticated_client.get("/api/api-keys")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []
        assert data["meta"]["count"] == 0

    @pytest.mark.asyncio
    async def test_create_api_key(self, authenticated_client: AsyncClient) -> None:
        """Create a new API key."""
        response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Test Key"},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Test Key"
        assert data["key"].startswith("tm_")
        assert data["key_prefix"] == data["key"][:11]
        assert data["is_active"] is True
        assert data["scopes"] is None

    @pytest.mark.asyncio
    async def test_create_api_key_with_scopes(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Create API key with scopes."""
        response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Scoped Key", "scopes": ["read", "write"]},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["scopes"] == ["read", "write"]

    @pytest.mark.asyncio
    async def test_get_api_key(self, authenticated_client: AsyncClient) -> None:
        """Get API key by ID."""
        # Create a key first
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Get Test"},
        )
        key_id = create_response.json()["data"]["id"]

        # Get it
        response = await authenticated_client.get(f"/api/api-keys/{key_id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Get Test"
        assert "key" not in data  # Secret not returned on get

    @pytest.mark.asyncio
    async def test_update_api_key(self, authenticated_client: AsyncClient) -> None:
        """Update API key name."""
        # Create a key first
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Original Name"},
        )
        key_id = create_response.json()["data"]["id"]

        # Update it
        response = await authenticated_client.put(
            f"/api/api-keys/{key_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_api_key(self, authenticated_client: AsyncClient) -> None:
        """Delete API key."""
        # Create a key first
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "To Delete"},
        )
        key_id = create_response.json()["data"]["id"]

        # Delete it
        response = await authenticated_client.delete(f"/api/api-keys/{key_id}")
        assert response.status_code == 200
        assert response.json()["data"]["deleted"] is True

        # Verify it's gone
        get_response = await authenticated_client.get(f"/api/api-keys/{key_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, authenticated_client: AsyncClient) -> None:
        """Revoke (deactivate) API key."""
        # Create a key first
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "To Revoke"},
        )
        key_id = create_response.json()["data"]["id"]

        # Revoke it
        response = await authenticated_client.post(f"/api/api-keys/{key_id}/revoke")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_api_key_limit(self, authenticated_client: AsyncClient) -> None:
        """Cannot create more than 10 API keys."""
        # Create 10 keys
        for i in range(10):
            response = await authenticated_client.post(
                "/api/api-keys",
                json={"name": f"Key {i}"},
            )
            assert response.status_code == 201

        # 11th should fail
        response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Key 10"},
        )
        assert response.status_code == 400
        assert "LIMIT_001" in response.json()["detail"]["code"]


class TestApiKeyAuthentication:
    """Test using API keys for authentication.

    Note: API keys work with endpoints that use CurrentUserFlexible.
    We test against /api/oauth/clients which uses CurrentUserFlexible.
    """

    @pytest.mark.asyncio
    async def test_auth_with_x_api_key_header(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Can authenticate using X-API-Key header."""
        # Create an API key
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Auth Test"},
        )
        api_key = create_response.json()["data"]["key"]

        # Clear cookies to ensure we're not using session auth
        authenticated_client.cookies.clear()

        # Use API key to access an endpoint that uses CurrentUserFlexible
        response = await authenticated_client.get(
            "/api/oauth/clients",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_with_bearer_api_key(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Can authenticate using Authorization: Bearer with API key."""
        # Create an API key
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Bearer Test"},
        )
        api_key = create_response.json()["data"]["key"]

        # Clear cookies to ensure we're not using session auth
        authenticated_client.cookies.clear()

        # Use it as Bearer token
        response = await authenticated_client.get(
            "/api/oauth/clients",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_revoked_api_key_rejected(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Revoked API keys cannot authenticate."""
        # Create an API key
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Revoke Auth Test"},
        )
        api_key = create_response.json()["data"]["key"]
        key_id = create_response.json()["data"]["id"]

        # Revoke it
        await authenticated_client.post(f"/api/api-keys/{key_id}/revoke")

        # Clear cookies to ensure we're not using session auth
        authenticated_client.cookies.clear()

        # Try to use revoked key on endpoint that uses CurrentUserFlexible
        response = await authenticated_client.get(
            "/api/oauth/clients",
            headers={"X-API-Key": api_key},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, client: AsyncClient) -> None:
        """Invalid API keys are rejected."""
        # Test against endpoint that uses CurrentUserFlexible
        response = await client.get(
            "/api/oauth/clients",
            headers={"X-API-Key": "tm_invalid_key_that_does_not_exist"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_api_key_updates_last_used(
        self, authenticated_client: AsyncClient
    ) -> None:
        """Using API key updates last_used_at timestamp."""
        # Create an API key
        create_response = await authenticated_client.post(
            "/api/api-keys",
            json={"name": "Last Used Test"},
        )
        api_key = create_response.json()["data"]["key"]
        key_id = create_response.json()["data"]["id"]

        # Initially last_used_at should be None
        get_response = await authenticated_client.get(f"/api/api-keys/{key_id}")
        assert get_response.json()["data"]["last_used_at"] is None

        # Store session cookie before clearing
        session_cookie = authenticated_client.cookies.get("session")
        assert session_cookie is not None

        # Clear cookies and use API key on endpoint that uses CurrentUserFlexible
        authenticated_client.cookies.clear()
        await authenticated_client.get(
            "/api/oauth/clients",
            headers={"X-API-Key": api_key},
        )

        # Restore session cookie to check the key
        authenticated_client.cookies.set("session", session_cookie)

        # Now last_used_at should be set
        get_response = await authenticated_client.get(f"/api/api-keys/{key_id}")
        assert get_response.json()["data"]["last_used_at"] is not None
