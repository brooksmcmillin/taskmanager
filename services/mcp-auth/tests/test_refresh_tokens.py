"""Tests for MCP OAuth refresh token flow."""

import os
import time

import pytest

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

from mcp.server.auth.provider import RefreshToken  # noqa: E402
from mcp.shared.auth import OAuthClientInformationFull  # noqa: E402
from pydantic import AnyUrl  # noqa: E402
from taskmanager_sdk import TokenConfig  # noqa: E402

from mcp_auth.taskmanager_oauth_provider import (  # noqa: E402
    TaskManagerAuthSettings,
    TaskManagerOAuthProvider,
)


def _create_provider() -> TaskManagerOAuthProvider:
    """Create a provider instance for testing."""
    settings = TaskManagerAuthSettings(
        base_url="http://localhost:4321",
        client_id="test-client",
        client_secret="test-secret",  # pragma: allowlist secret
    )
    return TaskManagerOAuthProvider(
        settings=settings,
        server_url="http://localhost:9000",
    )


def _create_client(client_id: str = "test-client") -> OAuthClientInformationFull:
    """Create an OAuth client for testing."""
    return OAuthClientInformationFull(
        client_id=client_id,
        client_name="Test Client",
        redirect_uris=[AnyUrl("http://localhost:3000/callback")],
    )


def _create_refresh_token(
    token_str: str,
    client_id: str = "test-client",
    scopes: list[str] | None = None,
    expires_at: int | None = None,
) -> RefreshToken:
    """Create a RefreshToken for testing."""
    return RefreshToken(
        token=token_str,
        client_id=client_id,
        scopes=scopes or ["read"],
        expires_at=expires_at or (int(time.time()) + 86400),
    )


class TestRefreshTokenStorage:
    """Test refresh token storage in in-memory provider."""

    @pytest.mark.asyncio
    async def test_store_and_load_refresh_token(self) -> None:
        """Test that refresh tokens are stored and can be loaded."""
        provider = _create_provider()
        client = _create_client()

        token_str = "mcp_rt_test_token_abc123"
        refresh_token = _create_refresh_token(token_str, scopes=["read", "write"])
        provider.refresh_tokens[token_str] = refresh_token

        loaded = await provider.load_refresh_token(client, token_str)
        assert loaded is not None
        assert loaded.token == token_str
        assert loaded.client_id == "test-client"
        assert set(loaded.scopes) == {"read", "write"}

    @pytest.mark.asyncio
    async def test_load_nonexistent_refresh_token(self) -> None:
        """Test that loading a nonexistent refresh token returns None."""
        provider = _create_provider()
        client = _create_client()

        result = await provider.load_refresh_token(client, "nonexistent_token")
        assert result is None

    @pytest.mark.asyncio
    async def test_load_expired_refresh_token(self) -> None:
        """Test that loading an expired refresh token returns None and cleans up."""
        provider = _create_provider()
        client = _create_client()

        token_str = "mcp_rt_expired_token"
        refresh_token = _create_refresh_token(token_str, expires_at=int(time.time()) - 3600)
        provider.refresh_tokens[token_str] = refresh_token

        result = await provider.load_refresh_token(client, token_str)
        assert result is None
        # Token should be cleaned up
        assert token_str not in provider.refresh_tokens

    @pytest.mark.asyncio
    async def test_load_refresh_token_wrong_client(self) -> None:
        """Test that refresh token can't be loaded by wrong client."""
        provider = _create_provider()

        token_str = "mcp_rt_client_check"
        refresh_token = _create_refresh_token(token_str, client_id="client-a")
        provider.refresh_tokens[token_str] = refresh_token

        wrong_client = _create_client("client-b")
        result = await provider.load_refresh_token(wrong_client, token_str)
        assert result is None


class TestRefreshTokenExchange:
    """Test refresh token exchange flow."""

    @pytest.mark.asyncio
    async def test_exchange_refresh_token_returns_new_tokens(self) -> None:
        """Test that exchanging a refresh token returns new access + refresh tokens."""
        provider = _create_provider()
        client = _create_client()

        old_token_str = "mcp_rt_old_token"
        old_refresh = _create_refresh_token(old_token_str, scopes=["read", "write"])
        provider.refresh_tokens[old_token_str] = old_refresh

        result = await provider.exchange_refresh_token(
            client=client,
            refresh_token=old_refresh,
            scopes=["read", "write"],
        )

        # Should return new tokens
        assert result.access_token.startswith("mcp_")
        assert result.refresh_token is not None
        assert result.refresh_token.startswith("mcp_rt_")
        assert result.token_type == "Bearer"
        assert result.expires_in == TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS

        # Old refresh token should be invalidated (rotation)
        assert old_token_str not in provider.refresh_tokens

        # New tokens should be in storage
        assert result.access_token in provider.tokens
        assert result.refresh_token in provider.refresh_tokens

    @pytest.mark.asyncio
    async def test_exchange_refresh_token_scope_subset(self) -> None:
        """Test requesting a subset of scopes during refresh."""
        provider = _create_provider()
        client = _create_client()

        token_str = "mcp_rt_scope_test"
        old_refresh = _create_refresh_token(token_str, scopes=["read", "write", "admin"])
        provider.refresh_tokens[token_str] = old_refresh

        result = await provider.exchange_refresh_token(
            client=client,
            refresh_token=old_refresh,
            scopes=["read"],
        )

        assert result.scope == "read"

    @pytest.mark.asyncio
    async def test_exchange_refresh_token_rejects_scope_escalation(self) -> None:
        """Test that requesting scopes beyond original grant is rejected."""
        provider = _create_provider()
        client = _create_client()

        token_str = "mcp_rt_escalation_test"
        old_refresh = _create_refresh_token(token_str, scopes=["read"])
        provider.refresh_tokens[token_str] = old_refresh

        with pytest.raises(ValueError, match="Requested scopes exceed original grant"):
            await provider.exchange_refresh_token(
                client=client,
                refresh_token=old_refresh,
                scopes=["read", "admin"],
            )

    @pytest.mark.asyncio
    async def test_exchange_refresh_token_rotation(self) -> None:
        """Test that refresh token rotation works - old token invalidated on each exchange."""
        provider = _create_provider()
        client = _create_client()

        first_token_str = "mcp_rt_rotation_first"
        first_refresh = _create_refresh_token(first_token_str)
        provider.refresh_tokens[first_token_str] = first_refresh

        # First exchange
        result1 = await provider.exchange_refresh_token(
            client=client,
            refresh_token=first_refresh,
            scopes=["read"],
        )

        # First token is gone
        assert first_token_str not in provider.refresh_tokens

        # Second exchange with new token
        new_refresh_token_str = result1.refresh_token
        assert new_refresh_token_str is not None
        new_refresh = provider.refresh_tokens[new_refresh_token_str]

        result2 = await provider.exchange_refresh_token(
            client=client,
            refresh_token=new_refresh,
            scopes=["read"],
        )

        # Second token is also gone
        assert new_refresh_token_str not in provider.refresh_tokens
        # Third token exists
        assert result2.refresh_token in provider.refresh_tokens

    @pytest.mark.asyncio
    async def test_refresh_token_has_correct_ttl(self) -> None:
        """Test that new refresh tokens have the correct TTL."""
        provider = _create_provider()
        client = _create_client()

        token_str = "mcp_rt_ttl_test"
        old_refresh = _create_refresh_token(token_str)
        provider.refresh_tokens[token_str] = old_refresh

        result = await provider.exchange_refresh_token(
            client=client,
            refresh_token=old_refresh,
            scopes=["read"],
        )

        assert result.refresh_token is not None
        new_rt = provider.refresh_tokens[result.refresh_token]
        expected_expiry = int(time.time()) + TokenConfig.MCP_REFRESH_TOKEN_TTL_SECONDS
        assert new_rt.expires_at is not None
        assert abs(new_rt.expires_at - expected_expiry) < 5


class TestAuthorizationCodeExchangeIssuesRefreshToken:
    """Test that exchange_authorization_code issues refresh tokens."""

    @pytest.mark.asyncio
    async def test_code_exchange_issues_both_tokens(self) -> None:
        """Test that exchanging an auth code returns both access and refresh tokens."""
        provider = _create_provider()
        client = _create_client()

        from mcp.server.auth.provider import AuthorizationCode
        from pydantic import AnyHttpUrl

        mcp_code = "mcp_test_auth_code"
        auth_code = AuthorizationCode(
            code=mcp_code,
            client_id="test-client",
            redirect_uri=AnyHttpUrl("http://localhost:3000/callback"),
            redirect_uri_provided_explicitly=True,
            expires_at=time.time() + 300,
            scopes=["read"],
            code_challenge="test-challenge",
        )
        provider.auth_codes[mcp_code] = auth_code

        result = await provider.exchange_authorization_code(
            client=client,
            authorization_code=auth_code,
        )

        assert result.access_token.startswith("mcp_")
        assert result.refresh_token is not None
        assert result.refresh_token.startswith("mcp_rt_")

        # Both should be stored in memory
        assert result.access_token in provider.tokens
        assert result.refresh_token in provider.refresh_tokens

    @pytest.mark.asyncio
    async def test_full_flow_auth_code_then_refresh(self) -> None:
        """Test the full flow: auth code exchange -> access token expires -> refresh."""
        provider = _create_provider()
        client = _create_client()

        from mcp.server.auth.provider import AuthorizationCode
        from pydantic import AnyHttpUrl

        # Step 1: Exchange authorization code
        mcp_code = "mcp_full_flow_code"
        auth_code = AuthorizationCode(
            code=mcp_code,
            client_id="test-client",
            redirect_uri=AnyHttpUrl("http://localhost:3000/callback"),
            redirect_uri_provided_explicitly=True,
            expires_at=time.time() + 300,
            scopes=["read", "write"],
            code_challenge="test-challenge",
        )
        provider.auth_codes[mcp_code] = auth_code

        initial_result = await provider.exchange_authorization_code(
            client=client,
            authorization_code=auth_code,
        )

        assert initial_result.refresh_token is not None
        initial_refresh_str = initial_result.refresh_token

        # Step 2: Use refresh token to get new tokens
        refresh_obj = provider.refresh_tokens[initial_refresh_str]

        refreshed_result = await provider.exchange_refresh_token(
            client=client,
            refresh_token=refresh_obj,
            scopes=["read", "write"],
        )

        # Old refresh token is invalidated
        assert initial_refresh_str not in provider.refresh_tokens

        # New tokens are valid
        assert refreshed_result.access_token in provider.tokens
        assert refreshed_result.refresh_token in provider.refresh_tokens
        assert refreshed_result.access_token != initial_result.access_token
        assert refreshed_result.refresh_token != initial_refresh_str
