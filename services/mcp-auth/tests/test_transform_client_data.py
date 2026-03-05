"""Unit tests for transform_client_data in auth_server module."""

import os

# Set required environment variables before importing modules that need them
os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")  # pragma: allowlist secret

from mcp_auth.auth_server import transform_client_data  # noqa: E402


class TestTransformClientData:
    """Tests for transform_client_data."""

    def test_returns_none_when_client_id_missing(self) -> None:
        result = transform_client_data({"name": "some-client"})
        assert result is None

    def test_public_client_no_secret_required(self) -> None:
        """Public clients (claude-code) should not need a secret."""
        result = transform_client_data(
            {
                "client_id": "test-id",
                "name": "claude-code-client",
            }
        )
        assert result is not None
        assert result["client_secret"] is None
        assert result["token_endpoint_auth_method"] == "none"

    def test_confidential_client_with_secret(self) -> None:
        """Confidential clients with a secret should work normally."""
        result = transform_client_data(
            {
                "client_id": "test-id",
                "name": "my-app",
                "client_secret": "real-secret",  # pragma: allowlist secret
            }
        )
        assert result is not None
        assert result["client_secret"] == "real-secret"  # pragma: allowlist secret
        assert result["token_endpoint_auth_method"] == "client_secret_post"

    def test_confidential_client_with_camel_case_secret(self) -> None:
        """Confidential clients using camelCase clientSecret field."""
        result = transform_client_data(
            {
                "client_id": "test-id",
                "name": "my-app",
                "clientSecret": "real-secret",  # pragma: allowlist secret
            }
        )
        assert result is not None
        assert result["client_secret"] == "real-secret"  # pragma: allowlist secret

    def test_confidential_client_without_secret_returns_none(self) -> None:
        """Confidential clients without a secret must be rejected (no dummy fallback)."""
        result = transform_client_data(
            {
                "client_id": "test-id",
                "name": "my-app",
            }
        )
        assert result is None

    def test_confidential_client_with_empty_secret_returns_none(self) -> None:
        """Confidential clients with an empty string secret must be rejected."""
        result = transform_client_data(
            {
                "client_id": "test-id",
                "name": "my-app",
                "client_secret": "",  # pragma: allowlist secret
            }
        )
        assert result is None
