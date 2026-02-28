"""Tests for OAuth 2.0 authorization endpoint."""

import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.models.oauth import AuthorizationCode, OAuthClient

TEST_CLIENT_SECRET = "test-client-secret-123"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def oauth_client(db_session):
    """Create a test OAuth client with authorization_code grant."""
    client = OAuthClient(
        client_id="test-client-id",
        client_secret_hash=hash_password(TEST_CLIENT_SECRET),
        name="Test Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["authorization_code", "refresh_token"]),
        scopes=json.dumps(["read", "write"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def inactive_oauth_client(db_session):
    """Create an inactive OAuth client."""
    client = OAuthClient(
        client_id="inactive-client",
        client_secret_hash=hash_password(TEST_CLIENT_SECRET),
        name="Inactive Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["authorization_code"]),
        scopes=json.dumps(["read"]),
        is_public=False,
        is_active=False,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def oauth_client_without_auth_code_grant(db_session):
    """Create an OAuth client without authorization_code grant type."""
    client = OAuthClient(
        client_id="client-no-auth-code",
        client_secret_hash=hash_password(TEST_CLIENT_SECRET),
        name="Client Without Auth Code",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["client_credentials"]),  # No authorization_code
        scopes=json.dumps(["read"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


# =============================================================================
# Authentication & Authorization Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_get_unauthenticated_redirects_to_login(
    client: AsyncClient, oauth_client
):
    """Test that unauthenticated GET shows login page with return_to."""
    response = await client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "state": "test-state",
        },
    )
    assert response.status_code == 200
    # Should show login page
    assert "login" in response.text.lower() or "sign in" in response.text.lower()
    # return_to should be in the page
    assert "return_to" in response.text


@pytest.mark.asyncio
async def test_authorize_get_authenticated_shows_consent(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that authenticated GET shows consent page."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
    )
    assert response.status_code == 200
    # Should show consent page with client name
    assert oauth_client.name in response.text or oauth_client.client_id in response.text
    # Should show scope
    assert "read" in response.text


@pytest.mark.asyncio
async def test_authorize_post_requires_authentication(
    client: AsyncClient, oauth_client
):
    """Test that POST requires authentication."""
    response = await client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    # Should return 401 (auth required)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_preserves_query_params_through_login(
    client: AsyncClient, oauth_client
):
    """Test that query params are preserved in return_to URL."""
    response = await client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
            "state": "test-state",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
        },
    )
    assert response.status_code == 200
    # Check that return_to contains all params
    assert "client_id=" in response.text
    assert "redirect_uri=" in response.text


@pytest.mark.asyncio
async def test_authorize_valid_session_shows_consent_with_scopes(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that valid session shows consent page with client name and scopes."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
        },
    )
    assert response.status_code == 200
    assert "read" in response.text
    assert "write" in response.text


# =============================================================================
# Client Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_invalid_client_id(authenticated_client: AsyncClient):
    """Test authorization with invalid client_id."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "nonexistent-client",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
    )
    assert response.status_code == 401
    assert (
        "invalid_client" in response.text.lower() or "client" in response.text.lower()
    )


@pytest.mark.asyncio
async def test_authorize_inactive_client_rejected(
    authenticated_client: AsyncClient, inactive_oauth_client
):
    """Test that inactive client is rejected."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": inactive_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_missing_client_id(authenticated_client: AsyncClient):
    """Test authorization with missing client_id parameter."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
    )
    # Should return 422 (validation error) for missing required param
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_authorize_sql_injection_in_client_id(authenticated_client: AsyncClient):
    """Test SQL injection attempts in client_id."""
    malicious_client_ids = [
        "' OR '1'='1",
        "1'; DROP TABLE oauth_clients; --",
        "' UNION SELECT * FROM users --",
    ]
    for malicious_id in malicious_client_ids:
        response = await authenticated_client.get(
            "/api/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": malicious_id,
                "redirect_uri": "http://localhost:3000/callback",
                "scope": "read",
            },
        )
        # Should return 401 (invalid client), not crash
        assert response.status_code == 401


# =============================================================================
# Redirect URI Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_invalid_redirect_uri_not_in_whitelist(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that redirect_uri not in whitelist is rejected WITHOUT redirect."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://evil.com/callback",
            "scope": "read",
        },
    )
    # Should return 400 error directly, NOT redirect to evil.com
    assert response.status_code == 400
    # Should NOT redirect to the attacker's URL
    assert response.headers.get("location") != "http://evil.com/callback"


@pytest.mark.asyncio
async def test_authorize_missing_redirect_uri(
    authenticated_client: AsyncClient, oauth_client
):
    """Test authorization with missing redirect_uri."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "scope": "read",
        },
    )
    # Should return 422 (validation error)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_authorize_redirect_uri_exact_match_required(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that redirect_uri requires exact match (no subdomain tricks)."""
    # OAuth client has http://localhost:3000/callback
    # Try with different paths or subdomains
    invalid_uris = [
        "http://localhost:3000/callback/evil",
        "http://evil.localhost:3000/callback",
        "http://localhost:3000/callback?extra=param",
    ]
    for invalid_uri in invalid_uris:
        response = await authenticated_client.get(
            "/api/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": oauth_client.client_id,
                "redirect_uri": invalid_uri,
                "scope": "read",
            },
        )
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorize_redirect_uri_case_sensitive(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that redirect_uri validation is case-sensitive."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/CALLBACK",  # Wrong case
            "scope": "read",
        },
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_authorize_redirect_uri_protocol_mismatch(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that protocol mismatch (http vs https) is rejected."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "redirect_uri": "https://localhost:3000/callback",  # https instead of http
            "scope": "read",
        },
    )
    assert response.status_code == 400


# =============================================================================
# Denial Flow Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_denial_redirects_with_error(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that denying authorization redirects with error=access_denied."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "deny",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "state": "test-state",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303  # See Other
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/callback")
    assert "error=access_denied" in location
    assert "state=test-state" in location


@pytest.mark.asyncio
async def test_authorize_denial_preserves_state(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that state parameter is preserved on denial."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "deny",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "state": "abc123",
        },
        follow_redirects=False,
    )
    location = response.headers["location"]
    assert "state=abc123" in location


@pytest.mark.asyncio
async def test_authorize_denial_no_code_created(
    authenticated_client: AsyncClient, oauth_client, db_session
):
    """Test that no authorization code is created in database on denial."""
    await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "deny",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    # Verify no auth code was created
    result = await db_session.execute(
        select(AuthorizationCode).where(
            AuthorizationCode.client_id == oauth_client.client_id
        )
    )
    codes = result.scalars().all()
    assert len(codes) == 0


# =============================================================================
# Approval Flow with PKCE Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_approval_creates_code_and_redirects(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that approving creates authorization code and redirects."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
            "state": "test-state",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/callback")
    assert "code=" in location
    assert "state=test-state" in location


@pytest.mark.asyncio
async def test_authorize_approval_stores_code_in_database(
    authenticated_client: AsyncClient, oauth_client, test_user, db_session
):
    """Test that authorization code is stored in database with correct fields."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read write",
        },
        follow_redirects=False,
    )
    # Extract code from redirect
    location = response.headers["location"]
    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    code = query_params["code"][0]

    # Verify in database
    result = await db_session.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == code)
    )
    auth_code = result.scalar_one()
    assert auth_code.client_id == oauth_client.client_id
    assert auth_code.user_id == test_user.id
    assert auth_code.redirect_uri == "http://localhost:3000/callback"
    assert json.loads(auth_code.scopes) == ["read", "write"]


@pytest.mark.asyncio
async def test_authorize_approval_with_pkce_s256(
    authenticated_client: AsyncClient, oauth_client, db_session
):
    """Test that PKCE challenge and method are stored (S256)."""
    # Test PKCE S256 challenge (not a real secret)  # pragma: allowlist secret
    pkce_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"

    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256",
        },
        follow_redirects=False,
    )
    # Extract code
    location = response.headers["location"]
    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    code = query_params["code"][0]

    # Verify PKCE stored
    result = await db_session.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == code)
    )
    auth_code = result.scalar_one()
    assert auth_code.code_challenge == pkce_challenge
    assert auth_code.code_challenge_method == "S256"


@pytest.mark.asyncio
async def test_authorize_approval_with_pkce_plain(
    authenticated_client: AsyncClient, oauth_client, db_session
):
    """Test that PKCE plain method is stored."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "code_challenge": "plain-challenge",
            "code_challenge_method": "plain",
        },
        follow_redirects=False,
    )
    location = response.headers["location"]
    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    code = query_params["code"][0]

    result = await db_session.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == code)
    )
    auth_code = result.scalar_one()
    assert auth_code.code_challenge == "plain-challenge"
    assert auth_code.code_challenge_method == "plain"


@pytest.mark.asyncio
async def test_authorize_code_expiry_set_correctly(
    authenticated_client: AsyncClient, oauth_client, db_session
):
    """Test that authorization code expiry is set correctly."""
    before_time = datetime.now(UTC)
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    after_time = datetime.now(UTC)

    # Extract code
    location = response.headers["location"]
    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    code = query_params["code"][0]

    # Verify expiry
    result = await db_session.execute(
        select(AuthorizationCode).where(AuthorizationCode.code == code)
    )
    auth_code = result.scalar_one()
    # Auth code should expire in the future (default: 10 minutes)
    assert auth_code.expires_at > before_time
    assert auth_code.expires_at > after_time


@pytest.mark.asyncio
async def test_authorize_state_preserved_on_approval(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that state parameter is preserved in redirect."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "state": "xyz789",
        },
        follow_redirects=False,
    )
    location = response.headers["location"]
    assert "state=xyz789" in location


# =============================================================================
# Security & Edge Cases Tests
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_unsupported_response_type(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that unsupported response_type is rejected with error."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "token",  # Not supported (implicit flow)
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    # Should redirect with error (307 is OK too)
    assert response.status_code in [303, 307]
    location = response.headers["location"]
    assert "error=unsupported_response_type" in location


@pytest.mark.asyncio
async def test_authorize_missing_response_type(authenticated_client: AsyncClient):
    """Test that missing response_type parameter returns validation error."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "client_id": "test-client-id",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_authorize_missing_redirect_uri_param(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that missing redirect_uri returns validation error."""
    response = await authenticated_client.get(
        "/api/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": oauth_client.client_id,
            "scope": "read",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_authorize_open_redirect_protection(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that open redirect is prevented for non-whitelisted URIs."""
    evil_uris = [
        "http://evil.com/callback",
        "https://attacker.com/steal",
        "javascript:alert('xss')",
    ]
    for evil_uri in evil_uris:
        response = await authenticated_client.get(
            "/api/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": oauth_client.client_id,
                "redirect_uri": evil_uri,
                "scope": "read",
            },
        )
        # Should return 400 error, NOT redirect
        assert response.status_code == 400
        # Should not redirect to evil URI
        assert response.headers.get("location") != evil_uri


@pytest.mark.asyncio
async def test_authorize_code_is_single_use(
    authenticated_client: AsyncClient, oauth_client, client
):
    """Test that authorization code can only be used once (via token exchange)."""
    # Create authorization code
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    location = response.headers["location"]
    parsed = urlparse(location)
    query_params = parse_qs(parsed.query)
    code = query_params["code"][0]

    # Exchange code for token (first time - should succeed)
    token_response1 = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "redirect_uri": "http://localhost:3000/callback",
        },
    )
    assert token_response1.status_code == 200

    # Try to use same code again (should fail)
    token_response2 = await client.post(
        "/api/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": oauth_client.client_id,
            "client_secret": TEST_CLIENT_SECRET,
            "redirect_uri": "http://localhost:3000/callback",
        },
    )
    assert token_response2.status_code == 400
    data = token_response2.json()
    # Check for error in either OAuth format or API format
    if "error" in data:
        assert data["error"] == "invalid_grant"
    elif "detail" in data:
        assert (
            "invalid" in str(data["detail"]).lower()
            or "grant" in str(data["detail"]).lower()
        )


@pytest.mark.asyncio
async def test_authorize_empty_scope_allowed(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that empty scope is handled (defaults to client's scopes)."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "",  # Empty scope
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "code=" in location


# =============================================================================
# POST /authorize redirect_uri Re-validation Security Tests (task #457)
# =============================================================================


@pytest.mark.asyncio
async def test_authorize_post_rejects_unregistered_redirect_uri_on_allow(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that POST /authorize rejects an unregistered redirect_uri on allow.

    Security: An attacker must not be able to inject an arbitrary redirect_uri
    in the form POST to capture the authorization code.
    """
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://evil.com/steal",
            "scope": "read",
            "state": "test-state",
        },
        follow_redirects=False,
    )
    # Must return an error, NOT redirect to the attacker's URI
    assert response.status_code == 400
    # Must not redirect to the evil URI
    assert response.headers.get("location", "") != "http://evil.com/steal"
    # Response should indicate invalid redirect
    assert "redirect" in response.text.lower() or "invalid" in response.text.lower()


@pytest.mark.asyncio
async def test_authorize_post_rejects_unregistered_redirect_uri_on_deny(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that POST /authorize rejects an unregistered redirect_uri on deny.

    Security: Even when the user denies consent, the attacker must not receive
    a redirect to their URI (which would leak the error response to them).
    """
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "deny",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://evil.com/steal",
            "scope": "read",
            "state": "test-state",
        },
        follow_redirects=False,
    )
    # Must return an error, NOT redirect to the attacker's URI
    assert response.status_code == 400
    assert response.headers.get("location", "") != "http://evil.com/steal"


@pytest.mark.asyncio
async def test_authorize_post_accepts_registered_redirect_uri(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that POST /authorize accepts a valid registered redirect_uri."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "state": "valid-state",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/callback")
    assert "code=" in location
    assert "state=valid-state" in location


@pytest.mark.asyncio
async def test_authorize_post_rejects_invalid_client_id(
    authenticated_client: AsyncClient,
):
    """Test that POST /authorize rejects an invalid client_id."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": "nonexistent-client",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_post_rejects_inactive_client(
    authenticated_client: AsyncClient, inactive_oauth_client
):
    """Test that POST /authorize rejects an inactive client."""
    response = await authenticated_client.post(
        "/api/oauth/authorize",
        data={
            "action": "allow",
            "client_id": inactive_oauth_client.client_id,
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
        },
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_post_no_open_redirect_on_allow(
    authenticated_client: AsyncClient, oauth_client
):
    """Test that various malicious redirect URIs are rejected in POST allow."""
    evil_uris = [
        "http://evil.com/callback",
        "https://attacker.com/steal",
        "http://localhost:3000/callback/extra",
        "http://localhost:3000.evil.com/callback",
    ]
    for evil_uri in evil_uris:
        response = await authenticated_client.post(
            "/api/oauth/authorize",
            data={
                "action": "allow",
                "client_id": oauth_client.client_id,
                "redirect_uri": evil_uri,
                "scope": "read",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400, f"Expected 400 for URI: {evil_uri}"
        assert response.headers.get("location", "") != evil_uri
