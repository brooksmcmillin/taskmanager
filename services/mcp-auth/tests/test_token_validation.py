"""Unit tests for token validation/introspection during OAuth callback flow."""

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

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


class TestValidateTaskManagerToken:
    """Test _validate_taskmanager_token method."""

    @pytest.mark.asyncio
    async def test_successful_validation(self) -> None:
        """Test that a valid token returns metadata from the verify endpoint."""
        provider = _create_provider()

        verify_response = {
            "valid": True,
            "client_id": "test-client",
            "user_id": 42,
            "scopes": '["read", "write"]',
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=verify_response)

        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        provider._session = mock_session

        result = await provider._validate_taskmanager_token("test-access-token")

        assert result["valid"] is True
        assert result["client_id"] == "test-client"
        assert result["user_id"] == 42
        assert result["expires_in"] == 3600

        # Verify the correct URL and headers were used
        mock_session.get.assert_called_once_with(
            "http://localhost:4321/api/oauth/verify",
            headers={"Authorization": "Bearer test-access-token"},
        )

    @pytest.mark.asyncio
    async def test_invalid_token_raises(self) -> None:
        """Test that an invalid token raises HTTPException."""
        from starlette.exceptions import HTTPException

        provider = _create_provider()

        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Invalid token")

        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        provider._session = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await provider._validate_taskmanager_token("bad-token")

        assert exc_info.value.status_code == 400
        assert "not valid" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_server_error_raises(self) -> None:
        """Test that a server error from verify endpoint raises HTTPException."""
        from starlette.exceptions import HTTPException

        provider = _create_provider()

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_cm)

        provider._session = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await provider._validate_taskmanager_token("some-token")

        assert exc_info.value.status_code == 400


class TestOAuthCallbackTokenValidation:
    """Test that handle_oauth_callback validates tokens and uses verified metadata."""

    @pytest.mark.asyncio
    async def test_callback_uses_validated_scopes_and_expiry(self) -> None:
        """Test that the callback stores tokens with validated scopes and expiration."""
        provider = _create_provider()

        # Set up state mapping
        state = "test-state-123"
        provider.state_mapping[state] = {
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test-challenge",
            "redirect_uri_provided_explicitly": "True",
            "client_id": "mcp-client-1",
            "resource": None,
        }

        # Mock the request
        mock_request = MagicMock()
        mock_request.query_params = {
            "code": "auth-code-123",
            "state": state,
        }

        # Mock token exchange to return an access token
        with (
            patch.object(
                provider,
                "_exchange_code_with_taskmanager",
                new_callable=AsyncMock,
                return_value="tm-access-token-abc",
            ),
            patch.object(
                provider,
                "_validate_taskmanager_token",
                new_callable=AsyncMock,
                return_value={
                    "valid": True,
                    "client_id": "test-client",
                    "user_id": 42,
                    "scopes": '["read", "write"]',
                    "expires_in": 7200,
                    "token_type": "Bearer",
                },
            ) as mock_validate,
        ):
            response = await provider.handle_oauth_callback(mock_request)

        # Verify validation was called with the received token
        mock_validate.assert_called_once_with("tm-access-token-abc")

        # Check the stored token uses validated metadata
        stored_token = provider.tokens.get("tm-access-token-abc")
        assert stored_token is not None
        assert stored_token.scopes == ["read", "write"]
        # Expiry should be based on validated expires_in (7200), not the default
        assert stored_token.expires_at is not None
        expected_expires_at = int(time.time()) + 7200
        assert abs(stored_token.expires_at - expected_expires_at) < 5

        # Verify redirect response
        assert response.status_code == 302

    @pytest.mark.asyncio
    async def test_callback_falls_back_on_unparseable_scopes(self) -> None:
        """Test that invalid scope JSON falls back to default MCP scope."""
        provider = _create_provider()

        state = "test-state-456"
        provider.state_mapping[state] = {
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test-challenge",
            "redirect_uri_provided_explicitly": "True",
            "client_id": "mcp-client-1",
            "resource": None,
        }

        mock_request = MagicMock()
        mock_request.query_params = {
            "code": "auth-code-456",
            "state": state,
        }

        with (
            patch.object(
                provider,
                "_exchange_code_with_taskmanager",
                new_callable=AsyncMock,
                return_value="tm-access-token-def",
            ),
            patch.object(
                provider,
                "_validate_taskmanager_token",
                new_callable=AsyncMock,
                return_value={
                    "valid": True,
                    "client_id": "test-client",
                    "user_id": 42,
                    "scopes": "not-valid-json{{{",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
        ):
            await provider.handle_oauth_callback(mock_request)

        stored_token = provider.tokens.get("tm-access-token-def")
        assert stored_token is not None
        # Should fall back to default MCP scope
        assert stored_token.scopes == ["read"]

    @pytest.mark.asyncio
    async def test_callback_falls_back_on_missing_expires_in(self) -> None:
        """Test that missing expires_in falls back to default TTL."""
        from taskmanager_sdk import TokenConfig

        provider = _create_provider()

        state = "test-state-789"
        provider.state_mapping[state] = {
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test-challenge",
            "redirect_uri_provided_explicitly": "True",
            "client_id": "mcp-client-1",
            "resource": None,
        }

        mock_request = MagicMock()
        mock_request.query_params = {
            "code": "auth-code-789",
            "state": state,
        }

        with (
            patch.object(
                provider,
                "_exchange_code_with_taskmanager",
                new_callable=AsyncMock,
                return_value="tm-access-token-ghi",
            ),
            patch.object(
                provider,
                "_validate_taskmanager_token",
                new_callable=AsyncMock,
                return_value={
                    "valid": True,
                    "client_id": "test-client",
                    "user_id": 42,
                    "scopes": '["read"]',
                    "token_type": "Bearer",
                    # No expires_in field
                },
            ),
        ):
            await provider.handle_oauth_callback(mock_request)

        stored_token = provider.tokens.get("tm-access-token-ghi")
        assert stored_token is not None
        # Should fall back to default MCP TTL
        assert stored_token.expires_at is not None
        expected_expires_at = int(time.time()) + TokenConfig.MCP_ACCESS_TOKEN_TTL_SECONDS
        assert abs(stored_token.expires_at - expected_expires_at) < 5

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_token(self) -> None:
        """Test that the callback fails if token validation rejects the token."""
        from starlette.exceptions import HTTPException

        provider = _create_provider()

        state = "test-state-bad"
        provider.state_mapping[state] = {
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test-challenge",
            "redirect_uri_provided_explicitly": "True",
            "client_id": "mcp-client-1",
            "resource": None,
        }

        mock_request = MagicMock()
        mock_request.query_params = {
            "code": "auth-code-bad",
            "state": state,
        }

        with (
            patch.object(
                provider,
                "_exchange_code_with_taskmanager",
                new_callable=AsyncMock,
                return_value="invalid-token",
            ),
            patch.object(
                provider,
                "_validate_taskmanager_token",
                new_callable=AsyncMock,
                side_effect=HTTPException(400, "Token validation failed"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            await provider.handle_oauth_callback(mock_request)

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_callback_handles_list_scopes(self) -> None:
        """Test that scopes returned as a list (not JSON string) are handled."""
        provider = _create_provider()

        state = "test-state-list"
        provider.state_mapping[state] = {
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test-challenge",
            "redirect_uri_provided_explicitly": "True",
            "client_id": "mcp-client-1",
            "resource": None,
        }

        mock_request = MagicMock()
        mock_request.query_params = {
            "code": "auth-code-list",
            "state": state,
        }

        with (
            patch.object(
                provider,
                "_exchange_code_with_taskmanager",
                new_callable=AsyncMock,
                return_value="tm-access-token-list",
            ),
            patch.object(
                provider,
                "_validate_taskmanager_token",
                new_callable=AsyncMock,
                return_value={
                    "valid": True,
                    "client_id": "test-client",
                    "user_id": 42,
                    "scopes": ["read", "admin"],
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            ),
        ):
            await provider.handle_oauth_callback(mock_request)

        stored_token = provider.tokens.get("tm-access-token-list")
        assert stored_token is not None
        assert stored_token.scopes == ["read", "admin"]
