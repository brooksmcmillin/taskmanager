"""Tests for OAuth 2.0 device authorization flow endpoints."""

import json
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.oauth import DeviceCode, OAuthClient


@pytest_asyncio.fixture
async def device_oauth_client(db_session: AsyncSession) -> OAuthClient:
    """Create an OAuth client with device_code grant type."""
    client = OAuthClient(
        client_id="device-client-id",
        client_secret_hash=hash_password("device-secret"),  # pragma: allowlist secret
        name="Device Test Client",
        redirect_uris=json.dumps([]),
        grant_types=json.dumps(["device_code"]),
        scopes=json.dumps(["read", "write"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def oauth_client_no_device(db_session: AsyncSession) -> OAuthClient:
    """Create an OAuth client WITHOUT device_code grant type."""
    client = OAuthClient(
        client_id="no-device-client-id",
        client_secret_hash=hash_password("secret"),  # pragma: allowlist secret
        name="No Device Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["authorization_code"]),
        scopes=json.dumps(["read"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


# =============================================================================
# Device Authorization Request Tests (/device/code)
# =============================================================================


@pytest.mark.asyncio
async def test_device_authorization_success(
    client: AsyncClient, device_oauth_client: OAuthClient
):
    """Test successful device authorization request."""
    response = await client.post(
        "/api/oauth/device/code",
        data={
            "client_id": device_oauth_client.client_id,
            "scope": "read write",
        },
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response contains required fields
    assert "device_code" in data
    assert "user_code" in data
    assert "verification_uri" in data
    assert "verification_uri_complete" in data
    assert "expires_in" in data
    assert "interval" in data

    # Verify user code format (XXXX-XXXX)
    assert len(data["user_code"]) == 9
    assert data["user_code"][4] == "-"

    # Verify device code is long enough
    assert len(data["device_code"]) >= 32


@pytest.mark.asyncio
async def test_device_authorization_default_scope(
    client: AsyncClient, device_oauth_client: OAuthClient
):
    """Test device authorization with default scope."""
    response = await client.post(
        "/api/oauth/device/code",
        data={
            "client_id": device_oauth_client.client_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "device_code" in data


@pytest.mark.asyncio
async def test_device_authorization_invalid_client(client: AsyncClient):
    """Test device authorization fails with invalid client_id."""
    response = await client.post(
        "/api/oauth/device/code",
        data={
            "client_id": "invalid-client-id",
            "scope": "read",
        },
    )

    assert response.status_code == 401
    assert "OAUTH_001" in str(response.json())


@pytest.mark.asyncio
async def test_device_authorization_unsupported_grant_type(
    client: AsyncClient, oauth_client_no_device: OAuthClient
):
    """Test device authorization fails when client doesn't support device_code grant."""
    response = await client.post(
        "/api/oauth/device/code",
        data={
            "client_id": oauth_client_no_device.client_id,
            "scope": "read",
        },
    )

    assert response.status_code == 400
    assert "OAUTH_007" in str(response.json())


@pytest.mark.asyncio
async def test_device_authorization_inactive_client(
    client: AsyncClient, db_session: AsyncSession
):
    """Test device authorization fails with inactive client."""
    # Create inactive client
    inactive_client = OAuthClient(
        client_id="inactive-client-id",
        client_secret_hash=hash_password("secret"),  # pragma: allowlist secret
        name="Inactive Client",
        redirect_uris=json.dumps([]),
        grant_types=json.dumps(["device_code"]),
        scopes=json.dumps(["read"]),
        is_public=False,
        is_active=False,
    )
    db_session.add(inactive_client)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/device/code",
        data={
            "client_id": inactive_client.client_id,
            "scope": "read",
        },
    )

    assert response.status_code == 401
    assert "OAUTH_001" in str(response.json())


# =============================================================================
# Device Code Lookup Tests (/device/lookup)
# =============================================================================


@pytest_asyncio.fixture
async def pending_device_code(
    db_session: AsyncSession, device_oauth_client: OAuthClient
) -> DeviceCode:
    """Create a pending device code."""
    dc = DeviceCode(
        device_code="test-device-code-123",
        user_code="ABCD-1234",
        client_id=device_oauth_client.client_id,
        scopes=json.dumps(["read", "write"]),
        status="pending",
        interval=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(dc)
    await db_session.commit()
    await db_session.refresh(dc)
    return dc


@pytest_asyncio.fixture
async def expired_device_code(
    db_session: AsyncSession, device_oauth_client: OAuthClient
) -> DeviceCode:
    """Create an expired device code."""
    dc = DeviceCode(
        device_code="expired-device-code-456",
        user_code="WXYZ-9876",
        client_id=device_oauth_client.client_id,
        scopes=json.dumps(["read"]),
        status="pending",
        interval=5,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(dc)
    await db_session.commit()
    await db_session.refresh(dc)
    return dc


@pytest.mark.asyncio
async def test_lookup_device_code_success(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    device_oauth_client: OAuthClient,
):
    """Test successful device code lookup."""
    response = await authenticated_client.get(
        "/api/oauth/device/lookup",
        params={"user_code": pending_device_code.user_code},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user_code"] == pending_device_code.user_code
    assert data["client_id"] == device_oauth_client.client_id
    assert data["client_name"] == device_oauth_client.name
    assert "scopes" in data
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_lookup_device_code_normalized(
    authenticated_client: AsyncClient, pending_device_code: DeviceCode
):
    """Test device code lookup with unnormalized user code."""
    # Try with lowercase and spaces
    response = await authenticated_client.get(
        "/api/oauth/device/lookup",
        params={"user_code": "abcd 1234"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["user_code"] == "ABCD-1234"


@pytest.mark.asyncio
async def test_lookup_device_code_unauthenticated(
    client: AsyncClient, pending_device_code: DeviceCode
):
    """Test device code lookup requires authentication."""
    response = await client.get(
        "/api/oauth/device/lookup",
        params={"user_code": pending_device_code.user_code},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_lookup_device_code_not_found(authenticated_client: AsyncClient):
    """Test device code lookup fails with invalid user code."""
    response = await authenticated_client.get(
        "/api/oauth/device/lookup",
        params={"user_code": "INVALID-CODE"},
    )

    assert response.status_code == 404
    assert "NOT_FOUND" in str(response.json())


@pytest.mark.asyncio
async def test_lookup_device_code_expired(
    authenticated_client: AsyncClient, expired_device_code: DeviceCode
):
    """Test device code lookup fails with expired code."""
    response = await authenticated_client.get(
        "/api/oauth/device/lookup",
        params={"user_code": expired_device_code.user_code},
    )

    assert response.status_code == 404
    assert "NOT_FOUND" in str(response.json())


@pytest.mark.asyncio
async def test_lookup_device_code_already_approved(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    device_oauth_client: OAuthClient,
):
    """Test device code lookup fails for already approved codes."""
    dc = DeviceCode(
        device_code="approved-device-code",
        user_code="APPV-1111",
        client_id=device_oauth_client.client_id,
        scopes=json.dumps(["read"]),
        status="approved",
        user_id=1,
        interval=5,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(dc)
    await db_session.commit()

    response = await authenticated_client.get(
        "/api/oauth/device/lookup",
        params={"user_code": dc.user_code},
    )

    assert response.status_code == 404


# =============================================================================
# Device Authorization Tests (/device/authorize)
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_device_approve_json(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    db_session: AsyncSession,
):
    """Test device authorization approval with JSON request."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": pending_device_code.user_code,
            "action": "allow",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert "message" in data

    # Verify database was updated
    await db_session.commit()
    await db_session.refresh(pending_device_code)
    assert pending_device_code.status == "approved"
    assert pending_device_code.user_id is not None


@pytest.mark.asyncio
async def test_authorize_device_deny_json(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    db_session: AsyncSession,
):
    """Test device authorization denial with JSON request."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": pending_device_code.user_code,
            "action": "deny",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "denied"

    # Verify database was updated
    await db_session.commit()
    await db_session.refresh(pending_device_code)
    assert pending_device_code.status == "denied"
    assert pending_device_code.user_id is None


@pytest.mark.asyncio
async def test_authorize_device_approve_form(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    db_session: AsyncSession,
):
    """Test device authorization approval with form data."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        data={
            "user_code": pending_device_code.user_code,
            "action": "allow",
        },
        follow_redirects=False,
    )

    # Form requests redirect
    assert response.status_code == 307
    assert response.headers["location"] == "/oauth/device/success"

    # Verify database was updated
    await db_session.commit()
    await db_session.refresh(pending_device_code)
    assert pending_device_code.status == "approved"


@pytest.mark.asyncio
async def test_authorize_device_deny_form(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    db_session: AsyncSession,
):
    """Test device authorization denial with form data."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        data={
            "user_code": pending_device_code.user_code,
            "action": "deny",
        },
        follow_redirects=False,
    )

    # Form requests redirect
    assert response.status_code == 307
    assert response.headers["location"] == "/oauth/device/denied"

    # Verify database was updated
    await db_session.commit()
    await db_session.refresh(pending_device_code)
    assert pending_device_code.status == "denied"


@pytest.mark.asyncio
async def test_authorize_device_unauthenticated(
    client: AsyncClient, pending_device_code: DeviceCode
):
    """Test device authorization requires authentication."""
    response = await client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": pending_device_code.user_code,
            "action": "allow",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_device_missing_user_code(authenticated_client: AsyncClient):
    """Test device authorization fails without user_code."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "action": "allow",
        },
    )

    assert response.status_code == 400
    assert "VALIDATION" in str(response.json())


@pytest.mark.asyncio
async def test_authorize_device_missing_action(
    authenticated_client: AsyncClient, pending_device_code: DeviceCode
):
    """Test device authorization fails without action."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": pending_device_code.user_code,
        },
    )

    assert response.status_code == 400
    assert "VALIDATION" in str(response.json())


@pytest.mark.asyncio
async def test_authorize_device_invalid_user_code_json(
    authenticated_client: AsyncClient,
):
    """Test device authorization fails with invalid user code (JSON)."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": "INVALID-CODE",
            "action": "allow",
        },
    )

    assert response.status_code == 404
    assert "NOT_FOUND" in str(response.json())


@pytest.mark.asyncio
async def test_authorize_device_invalid_user_code_form(
    authenticated_client: AsyncClient,
):
    """Test device authorization fails with invalid user code (form)."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        data={
            "user_code": "INVALID-CODE",
            "action": "allow",
        },
        follow_redirects=False,
    )

    # Form requests redirect on error
    assert response.status_code == 307
    assert "error=invalid_code" in response.headers["location"]


@pytest.mark.asyncio
async def test_authorize_device_expired_code_json(
    authenticated_client: AsyncClient, expired_device_code: DeviceCode
):
    """Test device authorization fails with expired code (JSON)."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": expired_device_code.user_code,
            "action": "allow",
        },
    )

    assert response.status_code == 404
    assert "NOT_FOUND" in str(response.json())


@pytest.mark.asyncio
async def test_authorize_device_expired_code_form(
    authenticated_client: AsyncClient, expired_device_code: DeviceCode
):
    """Test device authorization fails with expired code (form)."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        data={
            "user_code": expired_device_code.user_code,
            "action": "allow",
        },
        follow_redirects=False,
    )

    # Form requests redirect on error
    assert response.status_code == 307
    assert "error=invalid_code" in response.headers["location"]


@pytest.mark.asyncio
async def test_authorize_device_normalized_user_code(
    authenticated_client: AsyncClient,
    pending_device_code: DeviceCode,
    db_session: AsyncSession,
):
    """Test device authorization normalizes user code."""
    # Use lowercase with spaces
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        json={
            "user_code": "abcd 1234",
            "action": "allow",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"

    # Verify correct device code was updated
    await db_session.commit()
    await db_session.refresh(pending_device_code)
    assert pending_device_code.status == "approved"


@pytest.mark.asyncio
async def test_authorize_device_invalid_content_type(
    authenticated_client: AsyncClient, pending_device_code: DeviceCode
):
    """Test device authorization fails with invalid content type."""
    response = await authenticated_client.post(
        "/api/oauth/device/authorize",
        content="invalid",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 400
    assert "VALIDATION" in str(response.json())
