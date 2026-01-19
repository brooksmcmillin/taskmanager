"""Unit tests for IntrospectionTokenVerifier class."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from mcp_resource_framework.auth import IntrospectionTokenVerifier


class TestIntrospectionTokenVerifier:
    def test_init(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
            validate_resource=True,
        )

        assert verifier.introspection_endpoint == "https://auth.example.com/introspect"
        assert verifier.server_url == "https://api.example.com"
        assert verifier.validate_resource is True
        assert verifier.resource_url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_verify_token_success(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "client_id": "client123",
            "scope": "read write",
            "exp": 1234567890,
            "aud": "https://api.example.com",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            token = await verifier.verify_token("test_token")

            assert token is not None
            assert token.token == "test_token"
            assert token.client_id == "client123"
            assert token.scopes == ["read", "write"]
            assert token.expires_at == 1234567890
            assert token.resource == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_verify_token_unsafe_endpoint(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="http://malicious.com/introspect",
            server_url="https://api.example.com",
        )

        token = await verifier.verify_token("test_token")

        assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_localhost_allowed(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="http://localhost:8080/introspect",
            server_url="https://api.example.com",
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"active": True, "client_id": "client123"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            token = await verifier.verify_token("test_token")

            assert token is not None

    @pytest.mark.asyncio
    async def test_verify_token_inactive(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"active": False}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            token = await verifier.verify_token("test_token")

            assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_http_error(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        mock_response = Mock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            token = await verifier.verify_token("test_token")

            assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_network_exception(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = httpx.RequestError("Network error")
            mock_client_class.return_value = mock_client

            token = await verifier.verify_token("test_token")

            assert token is None

    @pytest.mark.asyncio
    async def test_verify_token_with_resource_validation_success(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
            validate_resource=True,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "client_id": "client123",
            "aud": "https://api.example.com",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock the _validate_resource method to return True
            with patch.object(verifier, "_validate_resource", return_value=True):
                token = await verifier.verify_token("test_token")

            assert token is not None

    @pytest.mark.asyncio
    async def test_verify_token_with_resource_validation_failure(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
            validate_resource=True,
        )

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "active": True,
            "client_id": "client123",
            "aud": "https://other.example.com",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Mock the _validate_resource method to return False
            with patch.object(verifier, "_validate_resource", return_value=False):
                token = await verifier.verify_token("test_token")

            assert token is None

    def test_validate_resource_with_string_aud(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        token_data = {"aud": "https://api.example.com"}

        with patch.object(verifier, "_is_valid_resource", return_value=True) as mock_is_valid:
            result = verifier._validate_resource(token_data)

            assert result is True
            mock_is_valid.assert_called_once_with("https://api.example.com")

    def test_validate_resource_with_list_aud(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        token_data = {"aud": ["https://other.example.com", "https://api.example.com"]}

        with patch.object(verifier, "_is_valid_resource") as mock_is_valid:
            mock_is_valid.side_effect = lambda x: x == "https://api.example.com"

            result = verifier._validate_resource(token_data)

            assert result is True

    def test_validate_resource_with_list_aud_no_match(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        token_data = {"aud": ["https://other1.example.com", "https://other2.example.com"]}

        with patch.object(verifier, "_is_valid_resource", return_value=False):
            result = verifier._validate_resource(token_data)

            assert result is False

    def test_validate_resource_no_aud(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        token_data: dict[str, Any] = {}

        result = verifier._validate_resource(token_data)

        assert result is False

    def test_validate_resource_missing_urls(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect", server_url=""
        )

        token_data = {"aud": "https://api.example.com"}

        result = verifier._validate_resource(token_data)

        assert result is False

    def test_is_valid_resource_with_matching_resource(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect",
            server_url="https://api.example.com",
        )

        with patch(
            "mcp_resource_framework.auth.token_verifier.check_resource_allowed", return_value=True
        ) as mock_check:
            result = verifier._is_valid_resource("https://api.example.com")

            assert result is True
            mock_check.assert_called_once_with(
                requested_resource="https://api.example.com",
                configured_resource="https://api.example.com",
            )

    def test_is_valid_resource_no_resource_url(self) -> None:
        verifier = IntrospectionTokenVerifier(
            introspection_endpoint="https://auth.example.com/introspect", server_url=""
        )

        result = verifier._is_valid_resource("https://api.example.com")

        assert result is False
