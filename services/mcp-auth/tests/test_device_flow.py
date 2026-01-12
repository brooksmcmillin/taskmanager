"""Unit tests for OAuth2 Device Authorization Grant (RFC 8628) support."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")

from mcp_auth.taskmanager_oauth_provider import TaskManagerAuthSettings


class TestDeviceFlowMetadata:
    """Test OAuth metadata includes device authorization endpoint."""

    def test_metadata_includes_device_authorization_endpoint(self) -> None:
        """Test that OAuth metadata advertises device authorization endpoint."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.get("/.well-known/oauth-authorization-server")

            assert response.status_code == 200
            metadata = response.json()

            # Verify device authorization endpoint is advertised
            assert "device_authorization_endpoint" in metadata
            assert metadata["device_authorization_endpoint"] == "http://localhost:9000/device/code"

            # Verify device_code grant type is supported
            assert "grant_types_supported" in metadata
            assert (
                "urn:ietf:params:oauth:grant-type:device_code" in metadata["grant_types_supported"]
            )


class TestDeviceCodeEndpoint:
    """Test the /device/code endpoint."""

    @pytest.mark.asyncio
    async def test_device_code_request_missing_client_id(self) -> None:
        """Test that device code request without client_id returns error."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post("/device/code", data={})

            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "invalid_request"
            assert "client_id" in data["error_description"]

    @pytest.mark.asyncio
    async def test_device_code_request_proxies_to_taskmanager(self) -> None:
        """Test that device code request is proxied to TaskManager."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch("mcp_auth.auth_server.aiohttp.ClientSession") as mock_session_class,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            # Mock the aiohttp session for proxying - properly set up async context managers
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "device_code": "test-device-code-123",
                    "user_code": "ABCD-EFGH",
                    "verification_uri": "http://localhost:4321/oauth/device",
                    "verification_uri_complete": "http://localhost:4321/oauth/device?user_code=ABCD-EFGH",
                    "expires_in": 1800,
                    "interval": 5,
                }
            )

            # Create async context manager for the post response
            mock_post_cm = MagicMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_post_cm)

            # Create async context manager for the session
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/device/code",
                data={"client_id": "my-cli-client", "scope": "read"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["device_code"] == "test-device-code-123"
            assert data["user_code"] == "ABCD-EFGH"
            assert "verification_uri" in data


class TestDeviceCodeTokenExchange:
    """Test token exchange with device_code grant type."""

    @pytest.mark.asyncio
    async def test_device_code_token_exchange_missing_device_code(self) -> None:
        """Test that token exchange without device_code returns error."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "my-cli-client",
                },
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "invalid_request"
            assert "device_code" in data["error_description"]

    @pytest.mark.asyncio
    async def test_device_code_token_exchange_authorization_pending(self) -> None:
        """Test that authorization_pending error is forwarded."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch("mcp_auth.auth_server.aiohttp.ClientSession") as mock_session_class,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            # Mock TaskManager returning authorization_pending
            mock_response = MagicMock()
            mock_response.status = 400
            mock_response.json = AsyncMock(
                return_value={
                    "error": "authorization_pending",
                    "error_description": "User has not yet authorized the device",
                }
            )

            # Create async context manager for the post response
            mock_post_cm = MagicMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_post_cm)

            # Create async context manager for the session
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "my-cli-client",
                    "device_code": "test-device-code-123",
                },
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "authorization_pending"

    @pytest.mark.asyncio
    async def test_device_code_token_exchange_success(self) -> None:
        """Test successful device code token exchange issues MCP token."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch("mcp_auth.auth_server.aiohttp.ClientSession") as mock_session_class,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            # Mock TaskManager returning successful token
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(
                return_value={
                    "access_token": "taskmanager-access-token-xyz",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "taskmanager-refresh-token-xyz",
                    "scope": "read",
                }
            )

            # Create async context manager for the post response
            mock_post_cm = MagicMock()
            mock_post_cm.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post_cm.__aexit__ = AsyncMock(return_value=None)

            mock_session = MagicMock()
            mock_session.post = MagicMock(return_value=mock_post_cm)

            # Create async context manager for the session
            mock_session_cm = MagicMock()
            mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_cm.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session_cm

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "my-cli-client",
                    "device_code": "test-device-code-123",
                },
            )

            assert response.status_code == 200
            data = response.json()

            # Verify MCP token is issued (not TaskManager token)
            assert data["access_token"].startswith("mcp_")
            assert data["token_type"] == "Bearer"
            assert data["expires_in"] == 3600
            assert data["scope"] == "read"
            # Refresh token should be passed through
            assert data["refresh_token"] == "taskmanager-refresh-token-xyz"


class TestDeviceFlowSecurity:
    """Test security features for device flow endpoints."""

    def test_invalid_client_id_format_rejected(self) -> None:
        """Test that invalid client_id format is rejected."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)

            # Test with injection attempt in client_id
            response = client.post(
                "/device/code",
                data={"client_id": "client'; DROP TABLE users; --"},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "invalid_request"
            assert "Invalid client_id format" in data["error_description"]

    def test_invalid_device_code_format_rejected(self) -> None:
        """Test that invalid device_code format is rejected in token exchange."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)

            # Test with injection attempt in device_code
            response = client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "valid-client",
                    "device_code": "code\nwith\nnewlines",  # Invalid format
                },
            )

            assert response.status_code == 400
            data = response.json()
            assert data["error"] == "invalid_request"
            assert "Invalid device_code format" in data["error_description"]

    def test_rate_limiting_on_device_code_endpoint(self) -> None:
        """Test that rate limiting works on device code endpoint."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch("mcp_auth.auth_server.device_code_limiter") as mock_limiter,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            # Simulate rate limit exceeded
            mock_limiter.is_allowed.return_value = False
            mock_limiter.get_retry_after.return_value = 300

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/device/code",
                data={"client_id": "rate-limited-client"},
            )

            assert response.status_code == 429
            data = response.json()
            assert data["error"] == "slow_down"
            assert "Retry-After" in response.headers

    def test_rate_limiting_on_token_polling(self) -> None:
        """Test that rate limiting works on token polling."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch("mcp_auth.auth_server.token_poll_limiter") as mock_limiter,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret,
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            # Simulate rate limit exceeded
            mock_limiter.is_allowed.return_value = False
            mock_limiter.get_retry_after.return_value = 60

            from mcp_auth.auth_server import create_authorization_server

            auth_settings = TaskManagerAuthSettings(
                base_url="http://localhost:4321",
                client_id="test-client",
                client_secret="test-secret",  # pragma: allowlist secret
            )

            app = create_authorization_server(
                host="0.0.0.0",  # noqa: S104
                port=9000,
                server_url="http://localhost:9000",  # type: ignore[arg-type]
                auth_settings=auth_settings,
            )

            client = TestClient(app)
            response = client.post(
                "/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": "rate-limited-client",
                    "device_code": "valid-device-code-123",
                },
            )

            assert response.status_code == 400  # RFC 8628 uses 400 for slow_down
            data = response.json()
            assert data["error"] == "slow_down"
            assert "Retry-After" in response.headers


class TestRateLimiter:
    """Test the RateLimiter class directly."""

    def test_rate_limiter_allows_requests_within_limit(self) -> None:
        """Test that rate limiter allows requests within the limit."""
        from mcp_auth.auth_server import RateLimiter

        limiter = RateLimiter(requests_per_window=3, window_seconds=60)

        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False  # 4th request should be denied

    def test_rate_limiter_tracks_clients_separately(self) -> None:
        """Test that rate limiter tracks different clients separately."""
        from mcp_auth.auth_server import RateLimiter

        limiter = RateLimiter(requests_per_window=2, window_seconds=60)

        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False

        # Different client should have its own limit
        assert limiter.is_allowed("client2") is True
        assert limiter.is_allowed("client2") is True
        assert limiter.is_allowed("client2") is False

    def test_rate_limiter_retry_after(self) -> None:
        """Test that get_retry_after returns reasonable value."""
        from mcp_auth.auth_server import RateLimiter

        limiter = RateLimiter(requests_per_window=1, window_seconds=60)

        limiter.is_allowed("client1")  # Use up the quota
        retry_after = limiter.get_retry_after("client1")

        # Should be between 1 and 61 seconds
        assert 1 <= retry_after <= 61
