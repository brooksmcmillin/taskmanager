"""Unit tests for CIMD (Client ID Metadata Document) support."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

from mcp_auth.cimd import (  # noqa: E402
    CIMD_ALLOWED_AUTH_METHODS,
    CIMDFetcher,
    CIMDFetchError,
    CIMDValidationError,
)


class TestCIMDClientIdDetection:
    """Test detection of CIMD (URL-based) client_ids."""

    def test_detects_https_url(self) -> None:
        """Test that HTTPS URLs are detected as CIMD client_ids."""
        fetcher = CIMDFetcher()

        assert fetcher.is_cimd_client_id("https://example.com/oauth/metadata.json") is True
        assert fetcher.is_cimd_client_id("https://client.dev/oauth/client.json") is True
        assert fetcher.is_cimd_client_id("https://myapp.example.org/.well-known/oauth") is True

    def test_detects_localhost_http_when_allowed(self) -> None:
        """Test that localhost HTTP URLs are detected when allow_localhost is True."""
        fetcher = CIMDFetcher(allow_localhost=True)

        assert fetcher.is_cimd_client_id("http://localhost/oauth/metadata.json") is True
        assert fetcher.is_cimd_client_id("http://localhost:3000/callback") is True
        assert fetcher.is_cimd_client_id("http://127.0.0.1/oauth/client.json") is True

    def test_rejects_localhost_http_when_not_allowed(self) -> None:
        """Test that localhost HTTP URLs are rejected when allow_localhost is False."""
        fetcher = CIMDFetcher(allow_localhost=False)

        assert fetcher.is_cimd_client_id("http://localhost/oauth/metadata.json") is False
        assert fetcher.is_cimd_client_id("http://127.0.0.1/callback") is False

    def test_rejects_non_localhost_http(self) -> None:
        """Test that non-localhost HTTP URLs are always rejected."""
        fetcher = CIMDFetcher(allow_localhost=True)

        assert fetcher.is_cimd_client_id("http://example.com/oauth/metadata.json") is False
        assert fetcher.is_cimd_client_id("http://evil.com/oauth/client.json") is False

    def test_rejects_traditional_client_ids(self) -> None:
        """Test that traditional (non-URL) client_ids are not detected as CIMD."""
        fetcher = CIMDFetcher()

        assert fetcher.is_cimd_client_id("my-app-client") is False
        assert fetcher.is_cimd_client_id("client-123-abc") is False
        assert fetcher.is_cimd_client_id("claude-code-abcd1234") is False
        assert fetcher.is_cimd_client_id("") is False
        assert fetcher.is_cimd_client_id("not-a-url") is False

    def test_rejects_other_schemes(self) -> None:
        """Test that non-HTTP(S) schemes are rejected."""
        fetcher = CIMDFetcher()

        assert fetcher.is_cimd_client_id("ftp://example.com/oauth") is False
        assert fetcher.is_cimd_client_id("file:///path/to/file") is False
        assert fetcher.is_cimd_client_id("javascript:alert(1)") is False


class TestCIMDMetadataValidation:
    """Test validation of CIMD metadata documents."""

    def test_validates_matching_client_id(self) -> None:
        """Test that client_id in document must match the URL."""
        fetcher = CIMDFetcher()

        # Valid - client_id matches URL
        valid_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
        }
        fetcher._validate_metadata("https://example.com/oauth/metadata.json", valid_metadata)

    def test_rejects_mismatched_client_id(self) -> None:
        """Test that mismatched client_id is rejected."""
        fetcher = CIMDFetcher()

        invalid_metadata = {
            "client_id": "https://other.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
        }

        with pytest.raises(CIMDValidationError, match="client_id mismatch"):
            fetcher._validate_metadata("https://example.com/oauth/metadata.json", invalid_metadata)

    def test_requires_client_id(self) -> None:
        """Test that client_id is required."""
        fetcher = CIMDFetcher()

        invalid_metadata = {"redirect_uris": ["https://example.com/callback"]}

        with pytest.raises(CIMDValidationError, match="Missing required field: client_id"):
            fetcher._validate_metadata("https://example.com/oauth/metadata.json", invalid_metadata)

    def test_requires_redirect_uris(self) -> None:
        """Test that redirect_uris is required."""
        fetcher = CIMDFetcher()

        invalid_metadata = {"client_id": "https://example.com/oauth/metadata.json"}

        with pytest.raises(CIMDValidationError, match="Missing required field: redirect_uris"):
            fetcher._validate_metadata("https://example.com/oauth/metadata.json", invalid_metadata)

    def test_rejects_empty_redirect_uris(self) -> None:
        """Test that empty redirect_uris is rejected."""
        fetcher = CIMDFetcher()

        invalid_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": [],
        }

        with pytest.raises(CIMDValidationError, match="redirect_uris must be a non-empty array"):
            fetcher._validate_metadata("https://example.com/oauth/metadata.json", invalid_metadata)

    def test_allows_valid_auth_methods(self) -> None:
        """Test that valid authentication methods are accepted."""
        fetcher = CIMDFetcher()

        for auth_method in CIMD_ALLOWED_AUTH_METHODS:
            metadata = {
                "client_id": "https://example.com/oauth/metadata.json",
                "redirect_uris": ["https://example.com/callback"],
                "token_endpoint_auth_method": auth_method,
            }
            # Should not raise for "none"
            if auth_method == "none":
                fetcher._validate_metadata(
                    "https://example.com/oauth/metadata.json", metadata
                )

    def test_rejects_invalid_auth_methods(self) -> None:
        """Test that invalid authentication methods are rejected."""
        fetcher = CIMDFetcher()

        invalid_methods = ["client_secret_post", "client_secret_basic", "client_secret_jwt"]

        for auth_method in invalid_methods:
            invalid_metadata = {
                "client_id": "https://example.com/oauth/metadata.json",
                "redirect_uris": ["https://example.com/callback"],
                "token_endpoint_auth_method": auth_method,
            }

            with pytest.raises(CIMDValidationError, match="Invalid token_endpoint_auth_method"):
                fetcher._validate_metadata(
                    "https://example.com/oauth/metadata.json", invalid_metadata
                )

    def test_requires_jwks_for_private_key_jwt(self) -> None:
        """Test that private_key_jwt requires jwks or jwks_uri."""
        fetcher = CIMDFetcher()

        invalid_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "private_key_jwt",
        }

        with pytest.raises(CIMDValidationError, match="must provide jwks or jwks_uri"):
            fetcher._validate_metadata("https://example.com/oauth/metadata.json", invalid_metadata)

    def test_accepts_private_key_jwt_with_jwks(self) -> None:
        """Test that private_key_jwt with inline jwks is accepted."""
        fetcher = CIMDFetcher()

        valid_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "private_key_jwt",
            "jwks": {"keys": [{"kty": "RSA", "n": "...", "e": "AQAB"}]},
        }

        fetcher._validate_metadata("https://example.com/oauth/metadata.json", valid_metadata)

    def test_accepts_private_key_jwt_with_jwks_uri(self) -> None:
        """Test that private_key_jwt with jwks_uri is accepted."""
        fetcher = CIMDFetcher()

        valid_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "private_key_jwt",
            "jwks_uri": "https://example.com/.well-known/jwks.json",
        }

        fetcher._validate_metadata("https://example.com/oauth/metadata.json", valid_metadata)


class TestCIMDMetadataFetching:
    """Test fetching CIMD metadata documents."""

    @pytest.mark.asyncio
    async def test_fetches_and_validates_metadata(self) -> None:
        """Test successful metadata fetch and validation."""
        fetcher = CIMDFetcher()

        mock_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "client_name": "Example App",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "none",
        }

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read = AsyncMock(return_value=json.dumps(mock_metadata).encode())
        mock_response.json = AsyncMock(return_value=mock_metadata)

        mock_session = MagicMock()
        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with patch.object(fetcher, "_get_session", return_value=mock_session):
            metadata = await fetcher.fetch_metadata(
                "https://example.com/oauth/metadata.json", use_cache=False
            )

        assert metadata["client_id"] == "https://example.com/oauth/metadata.json"
        assert metadata["client_name"] == "Example App"
        assert metadata["redirect_uris"] == ["https://example.com/callback"]

    @pytest.mark.asyncio
    async def test_returns_cached_metadata(self) -> None:
        """Test that cached metadata is returned without network request."""
        fetcher = CIMDFetcher()

        # Pre-populate cache
        cached_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "redirect_uris": ["https://example.com/callback"],
        }
        await fetcher._set_cached("https://example.com/oauth/metadata.json", cached_metadata)

        # Mock session to verify it's not called
        mock_session = MagicMock()
        mock_session.get = MagicMock()

        with patch.object(fetcher, "_get_session", return_value=mock_session):
            metadata = await fetcher.fetch_metadata(
                "https://example.com/oauth/metadata.json", use_cache=True
            )

        assert metadata == cached_metadata
        mock_session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self) -> None:
        """Test that HTTP errors raise CIMDFetchError."""
        fetcher = CIMDFetcher()

        mock_response = MagicMock()
        mock_response.status = 404

        mock_session = MagicMock()
        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with (
            patch.object(fetcher, "_get_session", return_value=mock_session),
            pytest.raises(CIMDFetchError, match="HTTP 404"),
        ):
            await fetcher.fetch_metadata(
                "https://example.com/oauth/metadata.json", use_cache=False
            )

    @pytest.mark.asyncio
    async def test_rejects_oversized_document(self) -> None:
        """Test that oversized documents are rejected."""
        fetcher = CIMDFetcher(max_document_size=100)

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json", "Content-Length": "1000000"}

        mock_session = MagicMock()
        mock_get_cm = MagicMock()
        mock_get_cm.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_cm.__aexit__ = AsyncMock(return_value=None)
        mock_session.get = MagicMock(return_value=mock_get_cm)

        with (
            patch.object(fetcher, "_get_session", return_value=mock_session),
            pytest.raises(CIMDFetchError, match="exceeds maximum size"),
        ):
            await fetcher.fetch_metadata(
                "https://example.com/oauth/metadata.json", use_cache=False
            )


class TestCIMDClientInfo:
    """Test converting CIMD metadata to OAuth client information."""

    @pytest.mark.asyncio
    async def test_returns_none_for_non_cimd_client_id(self) -> None:
        """Test that non-CIMD client_ids return None."""
        fetcher = CIMDFetcher()

        result = await fetcher.get_client_info("my-traditional-client")
        assert result is None

    @pytest.mark.asyncio
    async def test_converts_metadata_to_client_info(self) -> None:
        """Test that metadata is converted to OAuthClientInformationFull."""
        fetcher = CIMDFetcher()

        mock_metadata = {
            "client_id": "https://example.com/oauth/metadata.json",
            "client_name": "Example App",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": "read write",
        }

        with patch.object(
            fetcher, "fetch_metadata", new_callable=AsyncMock, return_value=mock_metadata
        ):
            client_info = await fetcher.get_client_info(
                "https://example.com/oauth/metadata.json"
            )

        assert client_info is not None
        assert client_info.client_id == "https://example.com/oauth/metadata.json"
        assert client_info.client_secret is None  # CIMD clients never have secrets
        # redirect_uris are converted to AnyUrl objects by pydantic
        assert [str(uri) for uri in client_info.redirect_uris] == ["https://example.com/callback"]
        assert client_info.token_endpoint_auth_method == "none"
        assert client_info.scope == "read write"


class TestOAuthMetadataWithCIMD:
    """Test that OAuth metadata advertises CIMD support."""

    def test_metadata_includes_cimd_support(self) -> None:
        """Test that OAuth metadata advertises CIMD support."""
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                },
            ),
        ):
            mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])

            from starlette.testclient import TestClient

            from mcp_auth.auth_server import create_authorization_server
            from mcp_auth.taskmanager_oauth_provider import TaskManagerAuthSettings

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

            # Verify CIMD support is advertised
            assert metadata.get("client_id_metadata_document_supported") is True

            # Verify private_key_jwt is supported for CIMD confidential clients
            assert "private_key_jwt" in metadata.get("token_endpoint_auth_methods_supported", [])


class TestCIMDIntegrationWithProvider:
    """Test CIMD integration with the OAuth provider."""

    @pytest.mark.asyncio
    async def test_provider_get_client_uses_cimd_for_url_client_id(self) -> None:
        """Test that the provider uses CIMD fetcher for URL-based client_ids."""
        from mcp_auth.taskmanager_oauth_provider import (
            TaskManagerAuthSettings,
            TaskManagerOAuthProvider,
        )

        settings = TaskManagerAuthSettings(
            base_url="http://localhost:4321",
            client_id="server-client",
            client_secret="server-secret",  # pragma: allowlist secret
        )

        # Create a mock CIMD fetcher
        mock_cimd_fetcher = MagicMock()
        mock_cimd_fetcher.is_cimd_client_id.return_value = True

        mock_client_info = MagicMock()
        mock_client_info.client_id = "https://example.com/oauth/metadata.json"
        mock_client_info.client_secret = None
        mock_client_info.redirect_uris = ["https://example.com/callback"]
        mock_client_info.token_endpoint_auth_method = "none"

        mock_cimd_fetcher.get_client_info = AsyncMock(return_value=mock_client_info)

        provider = TaskManagerOAuthProvider(
            settings=settings,
            server_url="http://localhost:9000",
            cimd_fetcher=mock_cimd_fetcher,
        )

        # Get client using CIMD URL
        client = await provider.get_client("https://example.com/oauth/metadata.json")

        assert client is not None
        assert client.client_id == "https://example.com/oauth/metadata.json"
        mock_cimd_fetcher.is_cimd_client_id.assert_called_with(
            "https://example.com/oauth/metadata.json"
        )
        mock_cimd_fetcher.get_client_info.assert_called_with(
            "https://example.com/oauth/metadata.json"
        )

    @pytest.mark.asyncio
    async def test_provider_falls_back_for_traditional_client_id(self) -> None:
        """Test that the provider falls back to traditional lookup for non-CIMD client_ids."""
        from mcp_auth.taskmanager_oauth_provider import (
            TaskManagerAuthSettings,
            TaskManagerOAuthProvider,
        )

        settings = TaskManagerAuthSettings(
            base_url="http://localhost:4321",
            client_id="server-client",
            client_secret="server-secret",  # pragma: allowlist secret
        )

        # Create a mock CIMD fetcher that says this is not a CIMD client_id
        mock_cimd_fetcher = MagicMock()
        mock_cimd_fetcher.is_cimd_client_id.return_value = False

        provider = TaskManagerOAuthProvider(
            settings=settings,
            server_url="http://localhost:9000",
            cimd_fetcher=mock_cimd_fetcher,
        )

        # Add a traditional client to registered_clients
        provider.registered_clients["traditional-client"] = {
            "client_id": "traditional-client",
            "client_secret": "secret123",  # pragma: allowlist secret
            "redirect_uris": ["http://localhost/callback"],
            "response_types": ["code"],
            "grant_types": ["authorization_code"],
            "token_endpoint_auth_method": "client_secret_post",
            "scope": "read",
        }

        # Get client using traditional client_id
        client = await provider.get_client("traditional-client")

        assert client is not None
        assert client.client_id == "traditional-client"
        mock_cimd_fetcher.is_cimd_client_id.assert_called_with("traditional-client")
        mock_cimd_fetcher.get_client_info.assert_not_called()
