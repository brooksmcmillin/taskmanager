"""Unit tests for MCP client auto-registration with taskmanager backend (#185)."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

from mcp.shared.auth import OAuthClientInformationFull  # noqa: E402
from pydantic import AnyHttpUrl  # noqa: E402

from mcp_auth.taskmanager_oauth_provider import (  # noqa: E402
    TaskManagerAuthSettings,
    TaskManagerOAuthProvider,
)


def _create_provider(
    api_client: MagicMock | None = None,
) -> TaskManagerOAuthProvider:
    """Create a provider instance for testing."""
    settings = TaskManagerAuthSettings(
        base_url="http://localhost:4321",
        client_id="test-client",
        client_secret="test-secret",  # pragma: allowlist secret
    )
    return TaskManagerOAuthProvider(
        settings=settings,
        server_url="http://localhost:9000",
        api_client=api_client,
    )


def _create_client_info(
    client_id: str = "mcp-test-client",
    redirect_uris: list[str] | None = None,
    grant_types: list[str] | None = None,
    scope: str = "read write",
    auth_method: str = "none",
) -> OAuthClientInformationFull:
    """Create an OAuthClientInformationFull for testing."""
    return OAuthClientInformationFull(
        client_id=client_id,
        redirect_uris=[AnyHttpUrl(u) for u in (redirect_uris or ["http://localhost:3000/callback"])],
        grant_types=grant_types or ["authorization_code", "refresh_token"],
        scope=scope,
        token_endpoint_auth_method=auth_method,
    )


class TestRegisterClient:
    """Test register_client method."""

    @pytest.mark.asyncio
    async def test_stores_client_locally(self) -> None:
        """Client info is always stored in the local cache."""
        provider = _create_provider()
        client_info = _create_client_info()

        await provider.register_client(client_info)

        assert "mcp-test-client" in provider.clients
        assert provider.clients["mcp-test-client"] is client_info

    @pytest.mark.asyncio
    async def test_raises_on_missing_client_id(self) -> None:
        """Raises ValueError if client_id is None."""
        provider = _create_provider()
        client_info = _create_client_info()
        client_info.client_id = None  # type: ignore[assignment]

        with pytest.raises(ValueError, match="client_id is required"):
            await provider.register_client(client_info)

    @pytest.mark.asyncio
    async def test_auto_registers_when_api_client_present(self) -> None:
        """Calls _register_with_taskmanager when api_client is available."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999  # Far future
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id-123"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info()

        await provider.register_client(client_info)

        mock_api.create_system_oauth_client.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_auto_register_without_api_client(self) -> None:
        """Does not attempt backend registration when no api_client."""
        provider = _create_provider(api_client=None)
        client_info = _create_client_info()

        # Should not raise
        await provider.register_client(client_info)

        assert "mcp-test-client" in provider.clients


class TestRegisterWithTaskmanager:
    """Test _register_with_taskmanager method."""

    @pytest.mark.asyncio
    async def test_successful_registration(self) -> None:
        """Registers client with backend via SDK."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id-456"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info(
            client_id="my-mcp-client",
            redirect_uris=["http://localhost:3000/cb"],
            grant_types=["authorization_code"],
            scope="read write",
        )

        await provider._register_with_taskmanager(client_info)

        mock_api.create_system_oauth_client.assert_called_once_with(
            name="my-mcp-client",
            redirect_uris=["http://localhost:3000/cb"],
            grant_types=["authorization_code"],
            scopes=["read", "write"],
        )

    @pytest.mark.asyncio
    async def test_uses_client_name_when_available(self) -> None:
        """Uses client_name attribute if present on client_info."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info(client_id="id-123")
        client_info.client_name = "My MCP App"

        await provider._register_with_taskmanager(client_info)

        call_kwargs = mock_api.create_system_oauth_client.call_args[1]
        assert call_kwargs["name"] == "My MCP App"

    @pytest.mark.asyncio
    async def test_falls_back_to_client_id_for_name(self) -> None:
        """Falls back to client_id when client_name is not set."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info(client_id="fallback-id")

        await provider._register_with_taskmanager(client_info)

        call_kwargs = mock_api.create_system_oauth_client.call_args[1]
        assert call_kwargs["name"] == "fallback-id"

    @pytest.mark.asyncio
    async def test_no_valid_api_client(self) -> None:
        """Logs warning and returns when API client token is expired."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 0  # Already expired
        provider = _create_provider(api_client=mock_api)

        # Patch _ensure_valid_api_client to return None (expired)
        with patch.object(provider, "_ensure_valid_api_client", return_value=None):
            client_info = _create_client_info()
            await provider._register_with_taskmanager(client_info)

        mock_api.create_system_oauth_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_backend_returns_failure(self) -> None:
        """Logs warning when backend returns error response."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=False, error="Duplicate client"
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info()

        # Should not raise
        await provider._register_with_taskmanager(client_info)

    @pytest.mark.asyncio
    async def test_sdk_exception_handled(self) -> None:
        """Catches and logs exceptions from the SDK call."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.side_effect = ConnectionError("unreachable")
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info()

        # Should not raise
        await provider._register_with_taskmanager(client_info)

    @pytest.mark.asyncio
    async def test_default_scopes_when_scope_empty(self) -> None:
        """Uses default scopes when client_info.scope is empty."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info(scope="")

        await provider._register_with_taskmanager(client_info)

        call_kwargs = mock_api.create_system_oauth_client.call_args[1]
        assert call_kwargs["scopes"] == ["read"]

    @pytest.mark.asyncio
    async def test_default_grant_types_when_none(self) -> None:
        """Uses default grant_types when client_info.grant_types is None."""
        mock_api = MagicMock()
        mock_api.token_expires_at = 9999999999
        mock_api.create_system_oauth_client.return_value = MagicMock(
            success=True, data={"client_id": "backend-id"}
        )
        provider = _create_provider(api_client=mock_api)
        client_info = _create_client_info()
        client_info.grant_types = None  # type: ignore[assignment]

        await provider._register_with_taskmanager(client_info)

        call_kwargs = mock_api.create_system_oauth_client.call_args[1]
        assert call_kwargs["grant_types"] == ["authorization_code", "refresh_token"]
