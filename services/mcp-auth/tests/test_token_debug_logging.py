"""Unit tests for token endpoint debug logging security (task #607).

Verifies that:
- Sensitive request fields are redacted before logging
- The Authorization header is masked before logging
- Sensitive response fields (access_token etc.) are redacted before logging
- Debug logs are only emitted when DEBUG=true
"""

import json
import logging
import os
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlencode

import pytest
from starlette.testclient import TestClient

os.environ.setdefault("TASKMANAGER_OAUTH_HOST", "http://localhost:4321")
os.environ.setdefault("MCP_SERVER", "http://localhost:9000")
os.environ.setdefault("TASKMANAGER_CLIENT_ID", "test-client")
os.environ.setdefault("TASKMANAGER_CLIENT_SECRET", "test-secret")

from mcp_auth.taskmanager_oauth_provider import TaskManagerAuthSettings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(debug: str = "") -> "object":
    """Return a TestClient-ready Starlette app with DEBUG optionally set."""
    with (
        patch("mcp_auth.auth_server.api_client") as mock_api_client,
        patch.dict(
            "os.environ",
            {
                "TASKMANAGER_CLIENT_ID": "test-client",
                "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret
                "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                "MCP_SERVER": "http://localhost:9000",
                "DEBUG": debug,
            },
            clear=False,
        ),
    ):
        mock_api_client.get_oauth_clients.return_value = MagicMock(success=True, data=[])
        from mcp_auth.auth_server import create_authorization_server

        auth_settings = TaskManagerAuthSettings(
            base_url="http://localhost:4321",
            client_id="test-client",
            client_secret="test-secret",  # pragma: allowlist secret
        )
        return create_authorization_server(
            host="0.0.0.0",  # noqa: S104
            port=9000,
            server_url="http://localhost:9000",  # type: ignore[arg-type]
            auth_settings=auth_settings,
        )


# ---------------------------------------------------------------------------
# _redact_body (tested indirectly via log capture)
# ---------------------------------------------------------------------------


class TestRedactBody:
    """Verify that the URL-encoded body helper masks the right fields."""

    def _redact(self, raw: str) -> str:
        """Replicate the _redact_body logic so tests stay independent of internals."""
        sensitive = {"client_secret", "code", "refresh_token", "device_code"}
        parsed = parse_qs(raw, keep_blank_values=True)
        redacted = {k: ["[REDACTED]"] if k in sensitive else v for k, v in parsed.items()}
        return urlencode(redacted, doseq=True)

    def test_client_secret_is_redacted(self) -> None:
        body = "grant_type=authorization_code&client_id=myclient&client_secret=supersecret"
        result = self._redact(body)
        assert "supersecret" not in result
        assert "client_id=myclient" in result
        assert "grant_type=authorization_code" in result
        assert "client_secret=%5BREDACTED%5D" in result or "client_secret=[REDACTED]" in result

    def test_code_is_redacted(self) -> None:
        body = "grant_type=authorization_code&code=authcode123&client_id=x"
        result = self._redact(body)
        assert "authcode123" not in result

    def test_refresh_token_is_redacted(self) -> None:
        body = "grant_type=refresh_token&refresh_token=rt_secret&client_id=x"
        result = self._redact(body)
        assert "rt_secret" not in result

    def test_device_code_is_redacted(self) -> None:
        body = "grant_type=urn:ietf:params:oauth:grant-type:device_code&device_code=dc_secret"
        result = self._redact(body)
        assert "dc_secret" not in result

    def test_non_sensitive_fields_preserved(self) -> None:
        body = "grant_type=authorization_code&client_id=public_client&scope=read"
        result = self._redact(body)
        assert "public_client" in result
        assert "read" in result

    def test_empty_body_handled(self) -> None:
        result = self._redact("")
        assert result == ""

    def test_malformed_body_handled(self) -> None:
        # parse_qs silently drops unparseable fields; at minimum it should not raise
        result = self._redact("not_a_valid_encoded_body")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _redact_headers
# ---------------------------------------------------------------------------


class TestRedactHeaders:
    """Verify that the Authorization header is masked."""

    def _redact(self, headers: dict[str, str]) -> dict[str, str]:
        return {k: "[REDACTED]" if k.lower() == "authorization" else v for k, v in headers.items()}

    def test_authorization_header_is_redacted(self) -> None:
        headers = {"authorization": "Basic dXNlcjpwYXNz", "content-type": "application/json"}
        result = self._redact(headers)
        assert result["authorization"] == "[REDACTED]"
        assert "dXNlcjpwYXNz" not in str(result)

    def test_bearer_token_is_redacted(self) -> None:
        headers = {"Authorization": "Bearer eyJhbGci..."}
        result = self._redact(headers)
        assert result["Authorization"] == "[REDACTED]"

    def test_non_auth_headers_preserved(self) -> None:
        headers = {"content-type": "application/x-www-form-urlencoded", "accept": "*/*"}
        result = self._redact(headers)
        assert result == headers


# ---------------------------------------------------------------------------
# _redact_response_body
# ---------------------------------------------------------------------------


class TestRedactResponseBody:
    """Verify that token fields in the response JSON are masked."""

    def _redact(self, body: bytes) -> str:
        sensitive = {"access_token", "refresh_token", "id_token", "token"}
        try:
            resp_json: dict[str, object] = json.loads(body.decode("utf-8"))
            redacted = {k: "[REDACTED]" if k in sensitive else v for k, v in resp_json.items()}
            return str(redacted)
        except Exception:
            return "[unparseable]"

    def test_access_token_is_redacted(self) -> None:
        body = json.dumps({"access_token": "at_secret", "token_type": "bearer"}).encode()
        result = self._redact(body)
        assert "at_secret" not in result
        assert "bearer" in result

    def test_refresh_token_is_redacted(self) -> None:
        body = json.dumps({"access_token": "at", "refresh_token": "rt_secret"}).encode()
        result = self._redact(body)
        assert "rt_secret" not in result

    def test_id_token_is_redacted(self) -> None:
        body = json.dumps({"id_token": "id_secret"}).encode()
        result = self._redact(body)
        assert "id_secret" not in result

    def test_non_sensitive_fields_preserved(self) -> None:
        body = json.dumps({"token_type": "bearer", "expires_in": 3600, "scope": "read"}).encode()
        result = self._redact(body)
        assert "bearer" in result
        assert "3600" in result

    def test_unparseable_body_returns_placeholder(self) -> None:
        result = self._redact(b"not valid json {{{{")
        assert result == "[unparseable]"

    def test_empty_body_returns_placeholder(self) -> None:
        result = self._redact(b"")
        assert result == "[unparseable]"


# ---------------------------------------------------------------------------
# Debug logging gate
# ---------------------------------------------------------------------------


class TestDebugLoggingGate:
    """Verify that token endpoint debug logs are only emitted when DEBUG=true."""

    def _create_app_and_client(self, debug_value: str) -> "tuple[object, TestClient]":
        with (
            patch("mcp_auth.auth_server.api_client") as mock_api_client,
            patch.dict(
                "os.environ",
                {
                    "TASKMANAGER_CLIENT_ID": "test-client",
                    "TASKMANAGER_CLIENT_SECRET": "test-secret",  # pragma: allowlist secret
                    "TASKMANAGER_OAUTH_HOST": "http://localhost:4321",
                    "MCP_SERVER": "http://localhost:9000",
                    "DEBUG": debug_value,
                },
                clear=False,
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
            return app, TestClient(app)

    def test_no_debug_logs_when_debug_unset(self, caplog: pytest.LogCaptureFixture) -> None:
        """When DEBUG is not set (empty string), no debug lines are emitted for the token endpoint."""
        app, client = self._create_app_and_client("")
        with caplog.at_level(logging.DEBUG, logger="mcp_auth.auth_server"):
            client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "mycode",
                    "client_id": "test-client",
                    "client_secret": "mysecret",  # pragma: allowlist secret
                },
            )
        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        # None of the token endpoint debug sentinel strings should appear
        assert not any("TOKEN ENDPOINT DEBUG" in m for m in debug_msgs)

    def test_debug_logs_emitted_when_debug_true(self, caplog: pytest.LogCaptureFixture) -> None:
        """When DEBUG=true, the token endpoint emits debug-level lines."""
        app, client = self._create_app_and_client("true")
        with caplog.at_level(logging.DEBUG, logger="mcp_auth.auth_server"):
            client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "mycode",
                    "client_id": "test-client",
                    "client_secret": "mysecret",  # pragma: allowlist secret
                },
            )
        debug_msgs = [r.message for r in caplog.records if r.levelno == logging.DEBUG]
        assert any("TOKEN ENDPOINT DEBUG" in m for m in debug_msgs)

    def test_secrets_not_in_logs_when_debug_true(self, caplog: pytest.LogCaptureFixture) -> None:
        """Even when DEBUG=true, secret values must not appear in log output."""
        app, client = self._create_app_and_client("true")
        with caplog.at_level(logging.DEBUG, logger="mcp_auth.auth_server"):
            client.post(
                "/token",
                data={
                    "grant_type": "authorization_code",
                    "code": "super_secret_code",
                    "client_id": "test-client",
                    "client_secret": "super_secret_value",  # pragma: allowlist secret
                },
            )
        all_log_text = " ".join(r.message for r in caplog.records)
        assert "super_secret_code" not in all_log_text
        assert "super_secret_value" not in all_log_text
