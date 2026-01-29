"""Tests for OAuth 2.0 endpoints and flows."""

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.api.oauth.token import verify_pkce
from app.core.security import hash_password
from app.models.oauth import AccessToken, AuthorizationCode, DeviceCode, OAuthClient

# Test credentials
TEST_CLIENT_SECRET = "test-client-secret-123"  # pragma: allowlist secret
TEST_CODE_VERIFIER = "test-code-verifier-abc123xyz"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def oauth_client(db_session):
    """Create a test OAuth client."""

    client = OAuthClient(
        client_id="test-client-id",
        client_secret_hash=hash_password(TEST_CLIENT_SECRET),
        name="Test Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(
            ["authorization_code", "refresh_token", "client_credentials"]
        ),
        scopes=json.dumps(["read", "write"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def public_oauth_client(db_session):
    """Create a test public OAuth client (no client secret)."""
    client = OAuthClient(
        client_id="public-client-id",
        client_secret_hash=None,
        name="Public Test Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["authorization_code", "refresh_token"]),
        scopes=json.dumps(["read"]),
        is_public=True,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


# =============================================================================
# PKCE Verification Tests
# =============================================================================


def test_verify_pkce_plain():
    """Test PKCE verification with plain method."""
    code_verifier = "test-verifier"
    code_challenge = "test-verifier"
    assert verify_pkce(code_verifier, code_challenge, "plain") is True


def test_verify_pkce_plain_mismatch():
    """Test PKCE verification with plain method mismatch."""
    code_verifier = "test-verifier"
    code_challenge = "different-challenge"
    assert verify_pkce(code_verifier, code_challenge, "plain") is False


def test_verify_pkce_s256():
    """Test PKCE verification with S256 method."""
    code_verifier = TEST_CODE_VERIFIER
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    assert verify_pkce(code_verifier, code_challenge, "S256") is True


def test_verify_pkce_s256_mismatch():
    """Test PKCE verification with S256 method mismatch."""
    code_verifier = "test-verifier"
    code_challenge = "invalid-challenge"
    assert verify_pkce(code_verifier, code_challenge, "S256") is False


def test_verify_pkce_invalid_method():
    """Test PKCE verification with invalid method."""
    code_verifier = "test-verifier"
    code_challenge = "test-challenge"
    assert verify_pkce(code_verifier, code_challenge, "invalid") is False


# =============================================================================
# Token Endpoint - Authorization Code Grant
# =============================================================================


@pytest.mark.asyncio
async def test_authorization_code_grant_success(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test successful authorization code exchange."""
    # Create authorization code
    auth_code = AuthorizationCode(
        code="test-auth-code",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read", "write"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        code_challenge=None,
        code_challenge_method=None,
    )
    db_session.add(auth_code)
    await db_session.commit()

    # Exchange code for token
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "code": "test-auth-code",
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert "expires_in" in data
    assert data["scope"] == "read write"

    # Verify authorization code was deleted
    result = await db_session.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == "test-auth-code")
    )
    assert result.scalar_one_or_none() is None

    # Verify access token was created
    result = await db_session.execute(
        select(AccessToken).where(AccessToken.token == data["access_token"])
    )
    token = result.scalar_one_or_none()
    assert token is not None
    assert token.user_id == test_user.id


@pytest.mark.asyncio
async def test_authorization_code_grant_with_pkce_s256(
    client: AsyncClient, public_oauth_client, test_user, db_session
):
    """Test authorization code exchange with PKCE S256."""
    code_verifier = TEST_CODE_VERIFIER
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    # Create authorization code with PKCE
    auth_code = AuthorizationCode(
        code="test-pkce-code",
        client_id=public_oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    db_session.add(auth_code)
    await db_session.commit()

    # Exchange code with verifier
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": "test-pkce-code",
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": code_verifier,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["scope"] == "read"


@pytest.mark.asyncio
async def test_authorization_code_grant_pkce_missing_verifier(
    client: AsyncClient, public_oauth_client, test_user, db_session
):
    """Test authorization code exchange with PKCE but missing verifier."""
    digest = hashlib.sha256(b"test-verifier").digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    auth_code = AuthorizationCode(
        code="test-code",
        client_id=public_oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    db_session.add(auth_code)
    await db_session.commit()

    # Attempt without verifier
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": "test-code",
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"  # invalid_grant


@pytest.mark.asyncio
async def test_authorization_code_grant_invalid_pkce(
    client: AsyncClient, public_oauth_client, test_user, db_session
):
    """Test authorization code exchange with invalid PKCE verifier."""
    digest = hashlib.sha256(b"correct-verifier").digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    auth_code = AuthorizationCode(
        code="test-code",
        client_id=public_oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    db_session.add(auth_code)
    await db_session.commit()

    # Attempt with wrong verifier
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": public_oauth_client.client_id,
            "code": "test-code",
            "redirect_uri": "http://localhost:3000/callback",
            "code_verifier": "wrong-verifier",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


@pytest.mark.asyncio
async def test_authorization_code_grant_missing_code(client: AsyncClient, oauth_client):
    """Test token endpoint without authorization code."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"  # invalid_grant


@pytest.mark.asyncio
async def test_authorization_code_grant_invalid_code(client: AsyncClient, oauth_client):
    """Test token endpoint with invalid authorization code."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "code": "invalid-code",
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


@pytest.mark.asyncio
async def test_authorization_code_grant_expired_code(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test token endpoint with expired authorization code."""
    auth_code = AuthorizationCode(
        code="expired-code",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
    )
    db_session.add(auth_code)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "code": "expired-code",
            "redirect_uri": "http://localhost:3000/callback",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


@pytest.mark.asyncio
async def test_authorization_code_grant_redirect_uri_mismatch(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test token endpoint with mismatched redirect URI."""
    auth_code = AuthorizationCode(
        code="test-code",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        redirect_uri="http://localhost:3000/callback",
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db_session.add(auth_code)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "code": "test-code",
            "redirect_uri": "http://different-domain.com/callback",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_002"  # invalid_redirect


# =============================================================================
# Token Endpoint - Refresh Token Grant
# =============================================================================


@pytest.mark.asyncio
async def test_refresh_token_grant_success(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test successful refresh token exchange."""
    # Create access token with refresh token
    old_access_token = AccessToken(
        token="old-access-token",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read", "write"]),
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired
        refresh_token="test-refresh-token",
        refresh_token_expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(old_access_token)
    await db_session.commit()

    # Use refresh token
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "refresh_token": "test-refresh-token",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] != "old-access-token"
    assert "refresh_token" in data
    assert data["refresh_token"] != "test-refresh-token"
    assert data["token_type"] == "Bearer"
    assert data["scope"] == "read write"

    # Verify old token was deleted
    result = await db_session.execute(
        select(AccessToken).where(AccessToken.token == "old-access-token")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_refresh_token_grant_missing_token(client: AsyncClient, oauth_client):
    """Test refresh token endpoint without refresh token."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


@pytest.mark.asyncio
async def test_refresh_token_grant_invalid_token(client: AsyncClient, oauth_client):
    """Test refresh token endpoint with invalid refresh token."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "refresh_token": "invalid-refresh-token",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


@pytest.mark.asyncio
async def test_refresh_token_grant_expired_token(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test refresh token endpoint with expired refresh token."""
    old_token = AccessToken(
        token="old-token",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        refresh_token="expired-refresh",  # pragma: allowlist secret
        refresh_token_expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired
    )
    db_session.add(old_token)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "refresh_token": "expired-refresh",  # pragma: allowlist secret
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


# =============================================================================
# Token Endpoint - Client Credentials Grant
# =============================================================================


@pytest.mark.asyncio
async def test_client_credentials_grant_success(
    client: AsyncClient, oauth_client, db_session
):
    """Test successful client credentials grant."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "scope": "read write",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" not in data  # No refresh token for client credentials
    assert data["token_type"] == "Bearer"
    assert data["scope"] == "read write"

    # Verify token was created without user_id
    result = await db_session.execute(
        select(AccessToken).where(AccessToken.token == data["access_token"])
    )
    token = result.scalar_one_or_none()
    assert token is not None
    assert token.user_id is None
    assert token.client_id == oauth_client.client_id


@pytest.mark.asyncio
async def test_client_credentials_grant_default_scope(
    client: AsyncClient, oauth_client, db_session
):
    """Test client credentials grant with default scope."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["scope"] == "read write"  # Default from client


@pytest.mark.asyncio
async def test_client_credentials_grant_not_allowed(
    client: AsyncClient, public_oauth_client
):
    """Test client credentials grant when not in allowed grant types."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": public_oauth_client.client_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_007"  # unsupported_grant_type


# =============================================================================
# Token Endpoint - Device Code Grant
# =============================================================================


@pytest.mark.asyncio
async def test_device_code_grant_success(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test successful device code grant."""
    # Create approved device code
    device_code_entry = DeviceCode(
        device_code="test-device-code",
        user_code="ABC123",
        client_id=oauth_client.client_id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        interval=5,
        status="approved",
        user_id=test_user.id,
    )
    db_session.add(device_code_entry)
    await db_session.commit()

    # Exchange device code for token
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "test-device-code",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["scope"] == "read"

    # Verify device code was deleted
    result = await db_session.execute(
        select(DeviceCode).where(DeviceCode.device_code == "test-device-code")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_device_code_grant_authorization_pending(
    client: AsyncClient, oauth_client, db_session
):
    """Test device code grant when authorization is pending."""
    device_code_entry = DeviceCode(
        device_code="pending-device-code",
        user_code="ABC123",
        client_id=oauth_client.client_id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        interval=5,
        status="pending",
    )
    db_session.add(device_code_entry)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "pending-device-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_008"  # authorization_pending


@pytest.mark.asyncio
async def test_device_code_grant_access_denied(
    client: AsyncClient, oauth_client, db_session
):
    """Test device code grant when user denied access."""
    device_code_entry = DeviceCode(
        device_code="denied-device-code",
        user_code="ABC123",
        client_id=oauth_client.client_id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        interval=5,
        status="denied",
    )
    db_session.add(device_code_entry)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "denied-device-code",
        },
    )

    assert response.status_code == 403  # Forbidden per OAuth 2.0 spec
    assert response.json()["detail"]["code"] == "OAUTH_006"  # access_denied

    # Verify device code was deleted
    result = await db_session.execute(
        select(DeviceCode).where(DeviceCode.device_code == "denied-device-code")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_device_code_grant_expired(client: AsyncClient, oauth_client, db_session):
    """Test device code grant with expired code."""
    device_code_entry = DeviceCode(
        device_code="expired-device-code",
        user_code="ABC123",
        client_id=oauth_client.client_id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # Expired
        interval=5,
        status="pending",
    )
    db_session.add(device_code_entry)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "expired-device-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_010"  # expired_token


@pytest.mark.asyncio
async def test_device_code_grant_slow_down(
    client: AsyncClient, oauth_client, db_session
):
    """Test device code grant with slow down error."""
    device_code_entry = DeviceCode(
        device_code="polling-device-code",
        user_code="ABC123",
        client_id=oauth_client.client_id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        interval=5,
        status="pending",
        last_poll_at=datetime.now(UTC) - timedelta(seconds=2),  # Polled 2 seconds ago
    )
    db_session.add(device_code_entry)
    await db_session.commit()

    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "polling-device-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_009"  # slow_down


@pytest.mark.asyncio
async def test_device_code_grant_invalid_code(client: AsyncClient, oauth_client):
    """Test device code grant with invalid device code."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "device_code": "invalid-device-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_004"


# =============================================================================
# Token Endpoint - Client Validation
# =============================================================================


@pytest.mark.asyncio
async def test_token_endpoint_invalid_client(client: AsyncClient):
    """Test token endpoint with invalid client_id."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "invalid-client-id",
            "client_secret": "invalid-secret",  # pragma: allowlist secret
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "OAUTH_001"  # invalid_client


@pytest.mark.asyncio
async def test_token_endpoint_wrong_client_secret(client: AsyncClient, oauth_client):
    """Test token endpoint with wrong client secret."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": oauth_client.client_id,
            "client_secret": "wrong-secret",  # pragma: allowlist secret
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "OAUTH_001"


@pytest.mark.asyncio
async def test_token_endpoint_missing_client_secret(client: AsyncClient, oauth_client):
    """Test token endpoint with missing client secret for confidential client."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": oauth_client.client_id,
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "OAUTH_001"


@pytest.mark.asyncio
async def test_token_endpoint_unsupported_grant_type(client: AsyncClient, oauth_client):
    """Test token endpoint with unsupported grant type."""
    response = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "password",  # Not supported
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OAUTH_007"


# =============================================================================
# Token Verification Endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_verify_token_success(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test successful token verification."""
    access_token = AccessToken(
        token="test-verify-token",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read", "write"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked=False,
    )
    db_session.add(access_token)
    await db_session.commit()

    response = await client.get(
        "/api/oauth/verify",
        headers={"Authorization": "Bearer test-verify-token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["client_id"] == oauth_client.client_id
    assert data["user_id"] == test_user.id
    assert data["scopes"] == json.dumps(["read", "write"])
    assert data["expires_in"] > 0
    assert data["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_verify_token_missing_authorization(client: AsyncClient):
    """Test token verification without Authorization header."""
    response = await client.get("/api/oauth/verify")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_verify_token_invalid_token(client: AsyncClient):
    """Test token verification with invalid token."""
    response = await client.get(
        "/api/oauth/verify",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_004"


@pytest.mark.asyncio
async def test_verify_token_expired(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test token verification with expired token."""
    access_token = AccessToken(
        token="expired-token",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # Expired
        revoked=False,
    )
    db_session.add(access_token)
    await db_session.commit()

    response = await client.get(
        "/api/oauth/verify",
        headers={"Authorization": "Bearer expired-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_004"


@pytest.mark.asyncio
async def test_verify_token_revoked(
    client: AsyncClient, oauth_client, test_user, db_session
):
    """Test token verification with revoked token."""
    access_token = AccessToken(
        token="revoked-token",
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        revoked=True,
    )
    db_session.add(access_token)
    await db_session.commit()

    response = await client.get(
        "/api/oauth/verify",
        headers={"Authorization": "Bearer revoked-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_004"
