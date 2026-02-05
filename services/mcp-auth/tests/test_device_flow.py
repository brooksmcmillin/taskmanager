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
            patch("mcp_auth.auth_server.get_cimd_fetcher") as mock_cimd_fetcher_getter,
            patch("mcp_auth.taskmanager_oauth_provider.get_cimd_fetcher") as mock_provider_cimd,
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
            # Set up mock API client with proper token_expires_at to avoid TypeError
            mock_api_client.token_expires_at = None  # None means no token validation

            # Mock CIMD fetcher to return False for all client_ids (traditional clients)
            mock_cimd_fetcher = MagicMock()
            mock_cimd_fetcher.is_cimd_client_id.return_value = False
            mock_cimd_fetcher_getter.return_value = mock_cimd_fetcher
            mock_provider_cimd.return_value = mock_cimd_fetcher

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
            patch("mcp_auth.auth_server.get_cimd_fetcher") as mock_cimd_fetcher_getter,
            patch("mcp_auth.taskmanager_oauth_provider.get_cimd_fetcher") as mock_provider_cimd,
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
            # Set up mock API client with proper token_expires_at to avoid TypeError
            mock_api_client.token_expires_at = None  # None means no token validation

            # Mock CIMD fetcher to return False for all client_ids (traditional clients)
            mock_cimd_fetcher = MagicMock()
            mock_cimd_fetcher.is_cimd_client_id.return_value = False
            mock_cimd_fetcher_getter.return_value = mock_cimd_fetcher
            mock_provider_cimd.return_value = mock_cimd_fetcher

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
            # Refresh token should be an MCP refresh token (not TaskManager's)
            assert data["refresh_token"].startswith("mcp_rt_")


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
        from mcp_auth_framework.rate_limiting import SlidingWindowRateLimiter as RateLimiter

        limiter = RateLimiter(requests_per_window=3, window_seconds=60)

        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False  # 4th request should be denied

    def test_rate_limiter_tracks_clients_separately(self) -> None:
        """Test that rate limiter tracks different clients separately."""
        from mcp_auth_framework.rate_limiting import SlidingWindowRateLimiter as RateLimiter

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
        from mcp_auth_framework.rate_limiting import SlidingWindowRateLimiter as RateLimiter

        limiter = RateLimiter(requests_per_window=1, window_seconds=60)

        limiter.is_allowed("client1")  # Use up the quota
        retry_after = limiter.get_retry_after("client1")

        # Should be between 1 and 61 seconds
        assert 1 <= retry_after <= 61


class TestErrorTransformation:
    """Test backend error to OAuth error transformation."""

    def test_transform_backend_error_with_oauth_001(self) -> None:
        """Test transformation of OAUTH_001 backend error to invalid_client."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {
            "detail": {"code": "OAUTH_001", "message": "Invalid client_id or client_secret"}
        }

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "invalid_client",
            "error_description": "Invalid client_id or client_secret",
        }

    def test_transform_backend_error_with_auth_001(self) -> None:
        """Test transformation of AUTH_001 backend error to invalid_client."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": {"code": "AUTH_001", "message": "Authentication failed"}}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "invalid_client",
            "error_description": "Authentication failed",
        }

    def test_transform_already_oauth_format(self) -> None:
        """Test that already-formatted OAuth errors pass through unchanged."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        oauth_error_input = {
            "error": "authorization_pending",
            "error_description": "User has not yet authorized",
        }

        oauth_error = transform_backend_error_to_oauth(oauth_error_input)

        assert oauth_error == oauth_error_input

    def test_transform_unknown_error_code(self) -> None:
        """Test transformation of unknown error code falls back to server_error."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": {"code": "UNKNOWN_CODE", "message": "Some error"}}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {"error": "server_error", "error_description": "Some error"}

    def test_transform_string_detail(self) -> None:
        """Test transformation when detail is a simple string."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": "Something went wrong"}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "server_error",
            "error_description": "Something went wrong",
        }

    def test_transform_malformed_response(self) -> None:
        """Test transformation of malformed response falls back to generic error."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        malformed_error = {"something": "unexpected"}

        oauth_error = transform_backend_error_to_oauth(malformed_error)

        assert oauth_error == {
            "error": "server_error",
            "error_description": "An error occurred",
        }

    def test_transform_authorization_pending(self) -> None:
        """Test transformation of OAUTH_008 to authorization_pending (RFC 8628)."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": {"code": "OAUTH_008", "message": "Authorization pending"}}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "authorization_pending",
            "error_description": "Authorization pending",
        }

    def test_transform_slow_down(self) -> None:
        """Test transformation of OAUTH_009 to slow_down (RFC 8628)."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": {"code": "OAUTH_009", "message": "Slow down"}}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {"error": "slow_down", "error_description": "Slow down"}

    def test_transform_expired_token(self) -> None:
        """Test transformation of OAUTH_010 to expired_token (RFC 8628)."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {"detail": {"code": "OAUTH_010", "message": "Device code has expired"}}

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "expired_token",
            "error_description": "Device code has expired",
        }

    def test_transform_access_denied(self) -> None:
        """Test transformation of OAUTH_006 to access_denied (RFC 8628)."""
        from mcp_auth.auth_server import transform_backend_error_to_oauth

        backend_error = {
            "detail": {"code": "OAUTH_006", "message": "Access denied by resource owner"}
        }

        oauth_error = transform_backend_error_to_oauth(backend_error)

        assert oauth_error == {
            "error": "access_denied",
            "error_description": "Access denied by resource owner",
        }
