"""Tests for GitHub OAuth authentication endpoints."""

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_provider import UserOAuthProvider
from app.models.user import User
from app.services.github_oauth import GitHubOAuthError, GitHubUser


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
async def test_github_authorize_redirect(client: AsyncClient):
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

    # Set up the state in the internal storage
    from app.api.oauth import github as github_module

    github_module._oauth_states["valid_state"] = {"return_to": "/dashboard"}

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
    assert user.username == "githubuser"

    # Verify OAuth provider was linked
    result = await db_session.execute(
        select(UserOAuthProvider).where(UserOAuthProvider.user_id == user.id)
    )
    provider = result.scalar_one_or_none()
    assert provider is not None
    assert provider.provider == "github"
    assert provider.provider_user_id == "12345"


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

    from app.api.oauth import github as github_module

    github_module._oauth_states["link_state"] = {"return_to": "/"}

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
        username="linkeduser",
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

    from app.api.oauth import github as github_module

    github_module._oauth_states["existing_state"] = {"return_to": "/"}

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
async def test_github_callback_no_email(client: AsyncClient):
    """Test callback when GitHub user has no email."""
    mock_github_user = GitHubUser(
        id="99999",
        login="noemailuser",
        email=None,  # No email
        avatar_url=None,
        name=None,
    )

    from app.api.oauth import github as github_module

    github_module._oauth_states["noemail_state"] = {"return_to": "/"}

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
async def test_github_callback_token_exchange_failure(client: AsyncClient):
    """Test callback when token exchange fails."""
    from app.api.oauth import github as github_module

    github_module._oauth_states["fail_state"] = {"return_to": "/"}

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


@pytest.mark.asyncio
async def test_unique_username_generation(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that unique usernames are generated when GitHub username is taken."""
    # Create a user with the same username as we'll get from GitHub
    existing_user = User(
        username="duplicateuser",
        email="existing@example.com",
        password_hash="$2b$12$test",  # pragma: allowlist secret
    )
    db_session.add(existing_user)
    await db_session.commit()

    mock_github_user = GitHubUser(
        id="55555",
        login="duplicateuser",  # Same username as existing user
        email="new@example.com",
        avatar_url=None,
        name=None,
    )

    from app.api.oauth import github as github_module

    github_module._oauth_states["dup_state"] = {"return_to": "/"}

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
            params={"code": "test_code", "state": "dup_state"},
            follow_redirects=False,
        )

        assert response.status_code == 302

    # Verify new user was created with a different username
    result = await db_session.execute(
        select(User).where(User.email == "new@example.com")
    )
    new_user = result.scalar_one_or_none()
    assert new_user is not None
    assert new_user.username != "duplicateuser"
    assert new_user.username.startswith("duplicateuser")
