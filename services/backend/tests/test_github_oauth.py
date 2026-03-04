"""Tests for GitHub OAuth authentication endpoints."""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oauth.github import OAUTH_STATE_NAMESPACE
from app.models.oauth_provider import UserOAuthProvider
from app.models.shared_state import SharedState
from app.models.user import User
from app.services.github_oauth import GitHubOAuthError, GitHubUser


async def _create_valid_state(
    db: AsyncSession, state_key: str, return_to: str = "/"
) -> None:
    """Helper to create a valid state with proper timestamp in the database."""
    now = datetime.now(UTC)
    entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key=state_key,
        value={"return_to": return_to},
        expires_at=now + timedelta(minutes=5),
    )
    db.add(entry)
    await db.flush()


@pytest.mark.asyncio
async def test_github_config_disabled(client: AsyncClient):
    """Test GitHub config endpoint when GitHub OAuth is not configured."""
    # GitHub is not configured in test environment by default
    response = await client.get("/api/auth/github/config")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["authorize_url"] is None


@pytest.mark.asyncio
async def test_github_config_enabled(client: AsyncClient):
    """Test GitHub config endpoint when GitHub OAuth is configured."""
    with (
        patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_client_id",
                "GITHUB_CLIENT_SECRET": "test_secret",  # pragma: allowlist secret
            },
        ),
        patch("app.api.oauth.github.is_github_configured", return_value=True),
    ):
        response = await client.get("/api/auth/github/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["authorize_url"] == "/api/auth/github/authorize"


@pytest.mark.asyncio
async def test_github_authorize_not_configured(client: AsyncClient):
    """Test authorize endpoint when GitHub is not configured."""
    response = await client.get(
        "/api/auth/github/authorize",
        params={"return_to": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "GITHUB_001"


@pytest.mark.asyncio
async def test_github_authorize_redirect(client: AsyncClient, db_session: AsyncSession):
    """Test authorize endpoint redirects to GitHub."""
    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.get_authorization_url",
            return_value="https://github.com/login/oauth/authorize?client_id=test",
        ),
    ):
        response = await client.get(
            "/api/auth/github/authorize",
            params={"return_to": "/dashboard"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "github.com" in response.headers["location"]


@pytest.mark.asyncio
async def test_github_authorize_validates_return_to(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that authorize endpoint validates return_to to prevent open redirect."""
    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.get_authorization_url",
            return_value="https://github.com/login/oauth/authorize?client_id=test",
        ),
    ):
        # Test with malicious URL
        response = await client.get(
            "/api/auth/github/authorize",
            params={"return_to": "https://evil.com/steal"},
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Check that the stored state in the database has "/"
        result = await db_session.execute(
            select(SharedState).where(
                SharedState.namespace == OAUTH_STATE_NAMESPACE,
            )
        )
        entries = result.scalars().all()
        if entries:
            assert entries[-1].value["return_to"] == "/"


@pytest.mark.asyncio
async def test_github_authorize_allows_relative_paths(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that authorize endpoint allows relative paths."""
    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.get_authorization_url",
            return_value="https://github.com/login/oauth/authorize?client_id=test",
        ),
    ):
        response = await client.get(
            "/api/auth/github/authorize",
            params={"return_to": "/dashboard"},
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Check that the stored state preserved the relative path
        result = await db_session.execute(
            select(SharedState).where(
                SharedState.namespace == OAUTH_STATE_NAMESPACE,
            )
        )
        entries = result.scalars().all()
        if entries:
            assert entries[-1].value["return_to"] == "/dashboard"


@pytest.mark.asyncio
async def test_github_callback_invalid_state(client: AsyncClient):
    """Test callback with invalid state parameter."""
    with patch("app.api.oauth.github.is_github_configured", return_value=True):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "invalid_state"},
            follow_redirects=False,
        )

        # Should redirect to login with error
        assert response.status_code == 302
        assert "error=" in response.headers["location"]


@pytest.mark.asyncio
async def test_github_callback_expired_state(
    client: AsyncClient, db_session: AsyncSession
):
    """Test callback with expired state parameter."""
    # Create an expired state (6 minutes old, beyond 5-minute limit)
    now = datetime.now(UTC)
    entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key="expired_state",
        value={"return_to": "/"},
        expires_at=now - timedelta(minutes=1),  # Already expired
    )
    db_session.add(entry)
    await db_session.flush()

    with patch("app.api.oauth.github.is_github_configured", return_value=True):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "expired_state"},
            follow_redirects=False,
        )

        # Should redirect to login with error
        assert response.status_code == 302
        assert "error=" in response.headers["location"]
        assert "expired" in response.headers["location"].lower()


@pytest.mark.asyncio
async def test_github_callback_github_error(client: AsyncClient):
    """Test callback when GitHub returns an error."""
    with patch("app.api.oauth.github.is_github_configured", return_value=True):
        response = await client.get(
            "/api/auth/github/callback",
            params={
                "error": "access_denied",
                "error_description": "User denied access",
                "state": "test_state",
            },
            follow_redirects=False,
        )

        # Should redirect to login with error
        assert response.status_code == 302
        assert "error=" in response.headers["location"]


@pytest.mark.asyncio
async def test_github_callback_creates_new_user(
    client: AsyncClient, db_session: AsyncSession
):
    """Test callback creates new user when GitHub account not linked."""
    mock_github_user = GitHubUser(
        id="12345",
        login="githubuser",
        email="github@example.com",
        avatar_url="https://github.com/avatar.png",
        name="GitHub User",
    )

    # Set up the state in the database
    await _create_valid_state(db_session, "valid_state", "/dashboard")

    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.exchange_code_for_token",
            new_callable=AsyncMock,
            return_value="mock_access_token",
        ),
        patch(
            "app.api.oauth.github.get_user_info",
            new_callable=AsyncMock,
            return_value=mock_github_user,
        ),
    ):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "valid_state"},
            follow_redirects=False,
        )

        # Should redirect to return_to URL
        assert response.status_code == 302
        assert response.headers["location"] == "/dashboard"

        # Should set session cookie
        assert "session" in response.cookies

    # Verify user was created
    result = await db_session.execute(
        select(User).where(User.email == "github@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.email == "github@example.com"

    # Verify OAuth provider was linked
    result = await db_session.execute(
        select(UserOAuthProvider).where(UserOAuthProvider.user_id == user.id)
    )
    provider = result.scalar_one_or_none()
    assert provider is not None
    assert provider.provider == "github"
    assert provider.provider_user_id == "12345"
    # Verify token is encrypted (not plain text)
    assert provider.access_token != "mock_access_token"
    assert provider.access_token is not None


@pytest.mark.asyncio
async def test_github_callback_links_existing_user(
    client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """Test callback links GitHub to existing user with matching email."""
    mock_github_user = GitHubUser(
        id="67890",
        login="existinguser",
        email=test_user.email,  # Same email as test_user
        avatar_url="https://github.com/avatar.png",
        name="Existing User",
    )

    await _create_valid_state(db_session, "link_state", "/")

    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.exchange_code_for_token",
            new_callable=AsyncMock,
            return_value="mock_access_token",
        ),
        patch(
            "app.api.oauth.github.get_user_info",
            new_callable=AsyncMock,
            return_value=mock_github_user,
        ),
    ):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "link_state"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    # Verify OAuth provider was linked to existing user
    result = await db_session.execute(
        select(UserOAuthProvider).where(UserOAuthProvider.user_id == test_user.id)
    )
    provider = result.scalar_one_or_none()
    assert provider is not None
    assert provider.provider == "github"
    assert provider.provider_user_id == "67890"


@pytest.mark.asyncio
async def test_github_callback_existing_github_user_login(
    client: AsyncClient, db_session: AsyncSession
):
    """Test callback logs in existing user with linked GitHub account."""
    # First, create a user with linked GitHub
    user = User(
        email="linked@example.com",
        password_hash="$2b$12$test",  # pragma: allowlist secret
    )
    db_session.add(user)
    await db_session.flush()

    provider = UserOAuthProvider(
        user_id=user.id,
        provider="github",
        provider_user_id="11111",
        provider_username="linkedgithub",
        provider_email="linked@example.com",
    )
    db_session.add(provider)
    await db_session.commit()

    mock_github_user = GitHubUser(
        id="11111",
        login="linkedgithub",
        email="linked@example.com",
        avatar_url="https://github.com/avatar.png",
        name="Linked User",
    )

    await _create_valid_state(db_session, "existing_state", "/")

    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.exchange_code_for_token",
            new_callable=AsyncMock,
            return_value="mock_access_token",
        ),
        patch(
            "app.api.oauth.github.get_user_info",
            new_callable=AsyncMock,
            return_value=mock_github_user,
        ),
    ):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "existing_state"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "session" in response.cookies


@pytest.mark.asyncio
async def test_github_callback_no_email(client: AsyncClient, db_session: AsyncSession):
    """Test callback when GitHub user has no email."""
    mock_github_user = GitHubUser(
        id="99999",
        login="noemailuser",
        email=None,  # No email
        avatar_url=None,
        name=None,
    )

    await _create_valid_state(db_session, "noemail_state", "/")

    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.exchange_code_for_token",
            new_callable=AsyncMock,
            return_value="mock_access_token",
        ),
        patch(
            "app.api.oauth.github.get_user_info",
            new_callable=AsyncMock,
            return_value=mock_github_user,
        ),
    ):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "test_code", "state": "noemail_state"},
            follow_redirects=False,
        )

        # Should redirect with error about email
        assert response.status_code == 302
        assert "error=" in response.headers["location"]
        assert "email" in response.headers["location"].lower()


@pytest.mark.asyncio
async def test_github_callback_token_exchange_failure(
    client: AsyncClient, db_session: AsyncSession
):
    """Test callback when token exchange fails."""
    await _create_valid_state(db_session, "fail_state", "/")

    with (
        patch("app.api.oauth.github.is_github_configured", return_value=True),
        patch(
            "app.api.oauth.github.exchange_code_for_token",
            new_callable=AsyncMock,
            side_effect=GitHubOAuthError("Token exchange failed"),
        ),
    ):
        response = await client.get(
            "/api/auth/github/callback",
            params={"code": "bad_code", "state": "fail_state"},
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "error=" in response.headers["location"]


@pytest.mark.asyncio
async def test_get_connected_providers(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """Test getting connected OAuth providers for authenticated user."""
    # Add a GitHub provider for the test user
    provider = UserOAuthProvider(
        user_id=test_user.id,
        provider="github",
        provider_user_id="12345",
        provider_username="testgithub",
        provider_email="test@github.com",
        avatar_url="https://github.com/avatar.png",
    )
    db_session.add(provider)
    await db_session.commit()

    response = await authenticated_client.get("/api/auth/github/providers")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["provider"] == "github"
    assert data[0]["provider_username"] == "testgithub"


@pytest.mark.asyncio
async def test_get_connected_providers_unauthenticated(client: AsyncClient):
    """Test getting connected providers without authentication."""
    response = await client.get("/api/auth/github/providers")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_disconnect_github(
    authenticated_client: AsyncClient, db_session: AsyncSession, test_user: User
):
    """Test disconnecting GitHub from user account."""
    # Add a GitHub provider for the test user
    provider = UserOAuthProvider(
        user_id=test_user.id,
        provider="github",
        provider_user_id="12345",
        provider_username="testgithub",
    )
    db_session.add(provider)
    await db_session.commit()

    response = await authenticated_client.delete("/api/auth/github/disconnect")

    assert response.status_code == 200
    assert response.json()["message"] == "GitHub disconnected successfully"

    # Verify provider was removed
    result = await db_session.execute(
        select(UserOAuthProvider).where(UserOAuthProvider.user_id == test_user.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_disconnect_github_not_connected(authenticated_client: AsyncClient):
    """Test disconnecting GitHub when not connected."""
    response = await authenticated_client.delete("/api/auth/github/disconnect")

    assert response.status_code == 404


# =============================================================================
# Token Encryption Tests
# =============================================================================


def test_token_encryption_roundtrip():
    """Test that tokens can be encrypted and decrypted."""
    from app.services.token_encryption import decrypt_token, encrypt_token

    original_token = "gho_test_access_token_12345"
    encrypted = encrypt_token(original_token)

    # Encrypted should be different from original
    assert encrypted != original_token
    assert encrypted is not None

    # Should decrypt back to original
    decrypted = decrypt_token(encrypted)
    assert decrypted == original_token


def test_token_encryption_empty_token():
    """Test handling of empty tokens."""
    from app.services.token_encryption import decrypt_token, encrypt_token

    assert encrypt_token("") == ""
    assert decrypt_token("") is None
    assert decrypt_token(None) is None  # type: ignore


def test_token_decryption_invalid_token():
    """Test that invalid encrypted tokens return None."""
    from app.services.token_encryption import decrypt_token

    assert decrypt_token("invalid_encrypted_token") is None
    assert decrypt_token("gAAAAA_not_valid_fernet") is None


def test_hkdf_key_derivation_produces_valid_fernet_key():
    """Test that HKDF key derivation produces a valid Fernet key."""
    from cryptography.fernet import Fernet

    from app.services.token_encryption import _get_encryption_key

    key = _get_encryption_key()

    # Must be bytes
    assert isinstance(key, bytes)

    # Must be a valid Fernet key (32 bytes base64url-encoded = 44 chars with padding)
    assert len(key) == 44

    # Must be usable with Fernet without raising an exception
    fernet = Fernet(key)
    assert fernet is not None


def test_hkdf_key_derivation_is_deterministic():
    """Test that HKDF key derivation is deterministic for the same secret."""
    from app.services.token_encryption import _get_encryption_key

    key1 = _get_encryption_key()
    key2 = _get_encryption_key()

    assert key1 == key2


def test_hkdf_different_secrets_produce_different_keys():
    """Test that different SECRET_KEY values produce different derived keys."""
    import unittest.mock

    from app.services.token_encryption import _get_encryption_key

    with unittest.mock.patch("app.services.token_encryption.settings") as mock_settings:
        mock_settings.secret_key = "secret-one"  # pragma: allowlist secret
        key1 = _get_encryption_key()

    with unittest.mock.patch("app.services.token_encryption.settings") as mock_settings:
        mock_settings.secret_key = "secret-two"  # pragma: allowlist secret
        key2 = _get_encryption_key()

    assert key1 != key2


def test_hkdf_token_not_decryptable_with_different_secret():
    """Test that tokens encrypted with one secret cannot be decrypted with another."""
    import unittest.mock

    from app.services.token_encryption import decrypt_token, encrypt_token

    original_token = "gho_sensitive_token_abc123"

    # Encrypt with one secret
    with unittest.mock.patch("app.services.token_encryption.settings") as mock_settings:
        mock_settings.secret_key = "first-secret-key"  # pragma: allowlist secret
        encrypted = encrypt_token(original_token)

    # Attempt to decrypt with a different secret
    with unittest.mock.patch("app.services.token_encryption.settings") as mock_settings:
        mock_settings.secret_key = "second-secret-key"  # pragma: allowlist secret
        result = decrypt_token(encrypted)

    assert result is None


# =============================================================================
# Return-to Validation Tests
# =============================================================================


def test_validate_return_to_rejects_external_urls():
    """Test that external URLs are rejected."""
    from app.api.oauth.github import _validate_return_to

    # Various malicious URLs should be rejected
    assert _validate_return_to("https://evil.com") == "/"
    assert _validate_return_to("http://evil.com/steal") == "/"
    assert _validate_return_to("//evil.com") == "/"
    assert _validate_return_to("javascript:alert(1)") == "/"
    assert _validate_return_to("ftp://evil.com") == "/"


def test_validate_return_to_allows_relative_paths():
    """Test that relative paths are allowed."""
    from app.api.oauth.github import _validate_return_to

    assert _validate_return_to("/") == "/"
    assert _validate_return_to("/dashboard") == "/dashboard"
    assert _validate_return_to("/oauth/callback") == "/oauth/callback"
    url_with_params = "/path/with/params?foo=bar"
    assert _validate_return_to(url_with_params) == url_with_params


def test_validate_return_to_rejects_invalid_paths():
    """Test that invalid paths are rejected."""
    from app.api.oauth.github import _validate_return_to

    assert _validate_return_to("") == "/"
    assert _validate_return_to("relative-path") == "/"  # Must start with /
    assert _validate_return_to("../escape") == "/"


# =============================================================================
# State Storage Tests (PostgreSQL-backed)
# =============================================================================


@pytest.mark.asyncio
async def test_validate_and_consume_state_valid(db_session: AsyncSession):
    """Test that valid states are accepted and consumed."""
    from app.api.oauth.github import _validate_and_consume_state

    await _create_valid_state(db_session, "test_valid", "/dashboard")

    result = await _validate_and_consume_state("test_valid", db_session)
    assert result is not None
    assert result["return_to"] == "/dashboard"

    # State should be consumed (removed)
    from sqlalchemy import select

    db_result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.key == "test_valid",
        )
    )
    assert db_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_validate_and_consume_state_expired(db_session: AsyncSession):
    """Test that expired states are rejected."""
    from app.api.oauth.github import _validate_and_consume_state

    # Create an expired state
    now = datetime.now(UTC)
    entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key="test_expired",
        value={"return_to": "/"},
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(entry)
    await db_session.flush()

    result = await _validate_and_consume_state("test_expired", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_validate_and_consume_state_nonexistent(db_session: AsyncSession):
    """Test that nonexistent states return None."""
    from app.api.oauth.github import _validate_and_consume_state

    result = await _validate_and_consume_state("nonexistent_state", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_oauth_state_stored_in_database(db_session: AsyncSession):
    """Test that OAuth state is properly stored in the database."""
    from app.api.oauth.github import _store_oauth_state

    await _store_oauth_state(db_session, "db_test_state", "/settings")
    await db_session.flush()

    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.key == "db_test_state",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.value["return_to"] == "/settings"
    assert entry.expires_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_cleanup_expired_states(db_session: AsyncSession):
    """Test that expired OAuth states are cleaned up."""
    from app.api.oauth.github import _cleanup_expired_states

    now = datetime.now(UTC)

    # Create one valid and one expired state
    valid_entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key="valid_state",
        value={"return_to": "/"},
        expires_at=now + timedelta(minutes=5),
    )
    expired_entry = SharedState(
        namespace=OAUTH_STATE_NAMESPACE,
        key="expired_cleanup_state",
        value={"return_to": "/"},
        expires_at=now - timedelta(minutes=1),
    )
    db_session.add(valid_entry)
    db_session.add(expired_entry)
    await db_session.flush()

    await _cleanup_expired_states(db_session)
    await db_session.flush()

    # Valid state should remain
    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.key == "valid_state",
        )
    )
    assert result.scalar_one_or_none() is not None

    # Expired state should be removed
    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == OAUTH_STATE_NAMESPACE,
            SharedState.key == "expired_cleanup_state",
        )
    )
    assert result.scalar_one_or_none() is None
