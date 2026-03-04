"""Tests for the public OAuth-protected REST API."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from mcp_relay.api import create_api_app
from mcp_relay.server import MessageStore


@dataclass
class FakeAccessToken:
    """Minimal AccessToken stand-in for tests."""

    token: str
    client_id: str
    scopes: list[str]
    expires_at: int | None = None
    resource: str | None = None


VALID_TOKEN = FakeAccessToken(
    token="valid-token",
    client_id="test-client",
    scopes=["read"],
)


@pytest.fixture
def store() -> MessageStore:
    return MessageStore()


@pytest.fixture
def mock_verifier() -> AsyncMock:
    """Token verifier that accepts 'valid-token' and rejects everything else."""
    verifier = AsyncMock()

    async def verify(token: str) -> FakeAccessToken | None:
        if token == "valid-token":
            return VALID_TOKEN
        return None

    verifier.verify_token = AsyncMock(side_effect=verify)
    return verifier


@pytest.fixture
def client(store: MessageStore, mock_verifier: AsyncMock) -> TestClient:
    app = create_api_app(store, mock_verifier)
    return TestClient(app)


def auth_headers(token: str = "valid-token") -> dict[str, str]:  # noqa: S107
    return {"Authorization": f"Bearer {token}"}


class TestOAuthMiddleware:
    """Test that the OAuth middleware enforces token auth."""

    def test_missing_auth_header(self, client: TestClient) -> None:
        resp = client.get("/channels")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["error"]

    def test_invalid_auth_scheme(self, client: TestClient) -> None:
        resp = client.get("/channels", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401
        assert "Missing" in resp.json()["error"]

    def test_invalid_token(self, client: TestClient) -> None:
        resp = client.get("/channels", headers=auth_headers("bad-token"))
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["error"]

    def test_valid_token_passes(self, client: TestClient) -> None:
        resp = client.get("/channels", headers=auth_headers())
        assert resp.status_code == 200


class TestApiChannels:
    """Tests for GET /channels."""

    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/channels", headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json() == {"channels": []}

    def test_with_data(self, client: TestClient, store: MessageStore) -> None:
        store.add("alpha", "msg1", "alice")
        store.add("beta", "msg2", "bob")

        resp = client.get("/channels", headers=auth_headers())
        data = resp.json()
        assert len(data["channels"]) == 2
        by_name = {c["name"]: c for c in data["channels"]}
        assert by_name["alpha"]["message_count"] == 1
        assert by_name["beta"]["message_count"] == 1


class TestApiMessages:
    """Tests for GET /channels/{channel}/messages."""

    def test_empty_channel(self, client: TestClient) -> None:
        resp = client.get("/channels/nonexistent/messages", headers=auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["count"] == 0

    def test_with_messages(self, client: TestClient, store: MessageStore) -> None:
        store.add("test", "hello", "alice")
        store.add("test", "world", "bob")

        resp = client.get("/channels/test/messages", headers=auth_headers())
        data = resp.json()
        assert data["count"] == 2
        assert data["messages"][0]["content"] == "hello"

    def test_limit(self, client: TestClient, store: MessageStore) -> None:
        for i in range(10):
            store.add("test", f"msg-{i}")

        resp = client.get("/channels/test/messages?limit=3", headers=auth_headers())
        data = resp.json()
        assert data["count"] == 3

    def test_invalid_limit(self, client: TestClient) -> None:
        resp = client.get("/channels/test/messages?limit=abc", headers=auth_headers())
        assert resp.status_code == 400
        assert "Invalid limit" in resp.json()["error"]

    def test_since_filter(self, client: TestClient, store: MessageStore) -> None:
        msg1 = store.add("test", "old")
        store.add("test", "new")

        resp = client.get(
            "/channels/test/messages",
            params={"since": msg1.timestamp},
            headers=auth_headers(),
        )
        data = resp.json()
        assert data["count"] == 1
        assert data["messages"][0]["content"] == "new"


class TestApiSend:
    """Tests for POST /channels/{channel}/messages."""

    def test_send_message(self, client: TestClient, store: MessageStore) -> None:
        resp = client.post(
            "/channels/test/messages",
            json={"content": "hello from api"},
            headers=auth_headers(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "hello from api"
        assert data["sender"] == "test-client"  # from OAuth client_id
        assert data["channel"] == "test"

        messages, _ = store.get("test")
        assert len(messages) == 1
        assert messages[0].sender == "test-client"

    def test_sender_from_client_id(self, client: TestClient) -> None:
        """Sender should always be derived from OAuth token, not request body."""
        resp = client.post(
            "/channels/test/messages",
            json={"content": "msg", "sender": "attacker"},
            headers=auth_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["sender"] == "test-client"

    def test_empty_content(self, client: TestClient) -> None:
        resp = client.post(
            "/channels/test/messages",
            json={"content": ""},
            headers=auth_headers(),
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    def test_missing_content(self, client: TestClient) -> None:
        resp = client.post(
            "/channels/test/messages",
            json={},
            headers=auth_headers(),
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    def test_invalid_json(self, client: TestClient) -> None:
        resp = client.post(
            "/channels/test/messages",
            content=b"not json",
            headers={"content-type": "application/json", **auth_headers()},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    def test_message_too_large(self, client: TestClient) -> None:
        resp = client.post(
            "/channels/test/messages",
            json={"content": "x" * 70000},
            headers=auth_headers(),
        )
        assert resp.status_code == 400
        assert "Message too large" in resp.json()["error"]


class TestApiClear:
    """Tests for POST /channels/{channel}/clear."""

    def test_clear_existing(self, client: TestClient, store: MessageStore) -> None:
        store.add("test", "msg1")
        store.add("test", "msg2")

        resp = client.post("/channels/test/clear", headers=auth_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] is True

        messages, _ = store.get("test")
        assert messages == []

    def test_clear_nonexistent(self, client: TestClient) -> None:
        resp = client.post("/channels/nonexistent/clear", headers=auth_headers())
        assert resp.status_code == 200
        assert resp.json()["cleared"] is False
