"""Unit tests for server module."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp_resource_framework.middleware import NormalizePathMiddleware


class TestNormalizePathMiddleware:
    """Tests for the NormalizePathMiddleware ASGI middleware."""

    @pytest.fixture
    def mock_app(self) -> AsyncMock:
        """Create a mock ASGI app."""
        return AsyncMock()

    @pytest.fixture
    def middleware(self, mock_app: AsyncMock) -> NormalizePathMiddleware:
        """Create middleware instance with mock app."""
        return NormalizePathMiddleware(mock_app)

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_path(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that trailing slashes are stripped from paths."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/mcp/",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        # Check that app was called with modified scope
        mock_app.assert_called_once()
        call_args = mock_app.call_args
        modified_scope = call_args[0][0]
        assert modified_scope["path"] == "/mcp"

    @pytest.mark.asyncio
    async def test_preserves_path_without_trailing_slash(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that paths without trailing slashes are preserved."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/mcp",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        modified_scope = call_args[0][0]
        assert modified_scope["path"] == "/mcp"

    @pytest.mark.asyncio
    async def test_preserves_root_path(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that root path '/' is not modified."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        modified_scope = call_args[0][0]
        assert modified_scope["path"] == "/"

    @pytest.mark.asyncio
    async def test_strips_trailing_slash_from_nested_path(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that trailing slashes are stripped from nested paths."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/api/v1/tasks/",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        modified_scope = call_args[0][0]
        assert modified_scope["path"] == "/api/v1/tasks"

    @pytest.mark.asyncio
    async def test_passes_through_non_http_requests(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that non-HTTP requests (e.g., websocket) pass through unchanged."""
        scope: dict[str, Any] = {
            "type": "websocket",
            "path": "/ws/",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        # For non-http, path should not be modified
        assert call_args[0][0]["path"] == "/ws/"

    @pytest.mark.asyncio
    async def test_preserves_other_scope_fields(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that other scope fields are preserved when modifying path."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/mcp/",
            "method": "POST",
            "headers": [(b"host", b"example.com")],
            "query_string": b"foo=bar",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        modified_scope = call_args[0][0]
        assert modified_scope["path"] == "/mcp"
        assert modified_scope["method"] == "POST"
        assert modified_scope["headers"] == [(b"host", b"example.com")]
        assert modified_scope["query_string"] == b"foo=bar"

    @pytest.mark.asyncio
    async def test_does_not_modify_original_scope(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that the original scope dict is not modified."""
        original_scope: dict[str, Any] = {
            "type": "http",
            "path": "/mcp/",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(original_scope, receive, send)

        # Original scope should be unchanged
        assert original_scope["path"] == "/mcp/"

    @pytest.mark.asyncio
    async def test_passes_receive_and_send_to_app(
        self, middleware: NormalizePathMiddleware, mock_app: AsyncMock
    ) -> None:
        """Test that receive and send are passed to the wrapped app."""
        scope: dict[str, Any] = {
            "type": "http",
            "path": "/mcp",
        }
        receive = AsyncMock()
        send = AsyncMock()

        await middleware(scope, receive, send)

        mock_app.assert_called_once()
        call_args = mock_app.call_args
        assert call_args[0][1] is receive
        assert call_args[0][2] is send


class TestTransportSecurityConfiguration:
    """Tests for transport security configuration in create_resource_server."""

    def test_allowed_host_extracted_from_server_url(self) -> None:
        """Test that allowed_hosts is correctly extracted from server_url."""
        from urllib.parse import urlparse

        server_url = "https://mcp.example.com"
        parsed = urlparse(server_url)

        assert parsed.netloc == "mcp.example.com"

    def test_allowed_host_includes_port_if_present(self) -> None:
        """Test that allowed_hosts includes port if present in URL."""
        from urllib.parse import urlparse

        server_url = "https://mcp.example.com:8443"
        parsed = urlparse(server_url)

        assert parsed.netloc == "mcp.example.com:8443"

    @patch("mcp_resource.server.IntrospectionTokenVerifier")
    @patch("mcp_resource.server.FastMCP")
    def test_create_resource_server_sets_transport_security(
        self, mock_fastmcp: MagicMock, mock_verifier: MagicMock
    ) -> None:
        """Test that create_resource_server configures transport_security with allowed_hosts."""
        from mcp_resource.server import create_resource_server

        mock_fastmcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_fastmcp_instance

        create_resource_server(
            port=8001,
            server_url="https://mcp.example.com",
            auth_server_url="http://auth-server:9000",
            auth_server_public_url="https://auth.example.com",
            oauth_strict=False,
        )

        # Verify FastMCP was called with transport_security
        mock_fastmcp.assert_called_once()
        call_kwargs = mock_fastmcp.call_args[1]

        assert "transport_security" in call_kwargs
        transport_security = call_kwargs["transport_security"]
        assert "mcp.example.com" in transport_security.allowed_hosts

    @patch("mcp_resource.server.IntrospectionTokenVerifier")
    @patch("mcp_resource.server.FastMCP")
    def test_create_resource_server_with_port_in_url(
        self, mock_fastmcp: MagicMock, mock_verifier: MagicMock
    ) -> None:
        """Test that allowed_hosts includes port when present in server_url."""
        from mcp_resource.server import create_resource_server

        mock_fastmcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_fastmcp_instance

        create_resource_server(
            port=8001,
            server_url="https://mcp.example.com:8443",
            auth_server_url="http://auth-server:9000",
            auth_server_public_url="https://auth.example.com",
            oauth_strict=False,
        )

        call_kwargs = mock_fastmcp.call_args[1]
        transport_security = call_kwargs["transport_security"]
        assert "mcp.example.com:8443" in transport_security.allowed_hosts
