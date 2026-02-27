"""Tests for the debug REST API and web UI."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from mcp_relay.debug import create_debug_app
from mcp_relay.server import MessageStore

TEST_TOKEN = "test-debug-token-12345"


@pytest.fixture
def store() -> MessageStore:
    return MessageStore()


@pytest.fixture
def client(store: MessageStore) -> TestClient:
    """Client for the debug app *without* token auth (simulates no-token config)."""
    app = create_debug_app(store)
    return TestClient(app)


@pytest.fixture
def auth_client(store: MessageStore) -> TestClient:
    """Client for the debug app *with* token auth enabled."""
    app = create_debug_app(store, token=TEST_TOKEN)
    return TestClient(app)


class TestDebugAuth:
    """Tests for token authentication on the debug app."""

    def test_rejects_missing_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["error"]

    def test_rejects_wrong_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    def test_accepts_correct_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200
        assert "MCP Relay Debug" in resp.text

    def test_api_requires_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/channels")
        assert resp.status_code == 401

    def test_api_works_with_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get(
            "/api/channels",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"channels": []}

    def test_no_token_config_allows_all(self, client: TestClient) -> None:
        """When no token is configured, all requests pass through."""
        resp = client.get("/")
        assert resp.status_code == 200


class TestDebugIndex:
    """Tests for the HTML debug UI page."""

    def test_returns_html(self, client: TestClient) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "MCP Relay Debug" in resp.text

    def test_contains_js(self, client: TestClient) -> None:
        resp = client.get("/")
        assert "<script>" in resp.text
        assert "loadChannels" in resp.text


class TestDebugChannelsAPI:
    """Tests for GET /api/channels."""

    def test_empty(self, client: TestClient) -> None:
        resp = client.get("/api/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"channels": []}

    def test_with_data(self, client: TestClient, store: MessageStore) -> None:
        store.add("alpha", "msg1", "alice")
        store.add("alpha", "msg2", "bob")
        store.add("beta", "msg3", "carol")

        resp = client.get("/api/channels")
        data = resp.json()
        assert len(data["channels"]) == 2

        by_name = {c["name"]: c for c in data["channels"]}
        assert by_name["alpha"]["message_count"] == 2
        assert by_name["beta"]["message_count"] == 1
        assert by_name["alpha"]["last_activity"] is not None
        assert by_name["beta"]["last_activity"] is not None


class TestDebugMessagesAPI:
    """Tests for GET /api/channels/{channel}/messages."""

    def test_empty_channel(self, client: TestClient) -> None:
        resp = client.get("/api/channels/nonexistent/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "nonexistent"
        assert data["messages"] == []
        assert data["count"] == 0

    def test_with_messages(self, client: TestClient, store: MessageStore) -> None:
        store.add("debug", "hello", "alice")
        store.add("debug", "world", "bob")

        resp = client.get("/api/channels/debug/messages")
        data = resp.json()
        assert data["channel"] == "debug"
        assert data["count"] == 2
        assert data["messages"][0]["content"] == "hello"
        assert data["messages"][0]["sender"] == "alice"
        assert data["messages"][1]["content"] == "world"
        assert data["messages"][1]["sender"] == "bob"

    def test_since_filter(self, client: TestClient, store: MessageStore) -> None:
        msg1 = store.add("debug", "old")
        store.add("debug", "new")

        resp = client.get("/api/channels/debug/messages", params={"since": msg1.timestamp})
        data = resp.json()
        assert data["count"] == 1
        assert data["messages"][0]["content"] == "new"

    def test_limit_parameter(self, client: TestClient, store: MessageStore) -> None:
        for i in range(10):
            store.add("debug", f"msg-{i}")

        resp = client.get("/api/channels/debug/messages?limit=3")
        data = resp.json()
        assert data["count"] == 3
        # Should return the last 3 messages
        assert data["messages"][0]["content"] == "msg-7"
        assert data["messages"][2]["content"] == "msg-9"

    def test_limit_zero_returns_default(self, client: TestClient, store: MessageStore) -> None:
        for i in range(5):
            store.add("debug", f"msg-{i}")

        resp = client.get("/api/channels/debug/messages?limit=0")
        data = resp.json()
        # limit=0 should be treated as the default (100), returning all 5 messages
        assert data["count"] == 5

    def test_invalid_limit(self, client: TestClient) -> None:
        resp = client.get("/api/channels/debug/messages?limit=abc")
        assert resp.status_code == 400
        assert "Invalid limit" in resp.json()["error"]

    def test_invalid_since(self, client: TestClient, store: MessageStore) -> None:
        store.add("test", "msg")
        resp = client.get("/api/channels/test/messages?since=not-a-date")
        assert resp.status_code == 400
        assert "Invalid ISO timestamp" in resp.json()["error"]

    def test_url_encoded_channel(self, client: TestClient, store: MessageStore) -> None:
        store.add("my-channel", "msg")
        resp = client.get("/api/channels/my-channel/messages")
        data = resp.json()
        assert data["channel"] == "my-channel"
        assert data["count"] == 1


class TestDebugSendAPI:
    """Tests for POST /api/channels/{channel}/messages."""

    def test_send_message(self, client: TestClient, store: MessageStore) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": "hello from debug", "sender": "tester"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "hello from debug"
        assert data["sender"] == "tester"
        assert data["channel"] == "test"
        assert "id" in data
        assert "timestamp" in data

        # Verify it's in the store
        messages = store.get("test")
        assert len(messages) == 1
        assert messages[0].content == "hello from debug"

    def test_send_default_sender(self, client: TestClient) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 201
        assert resp.json()["sender"] == "debug-ui"

    def test_send_empty_content(self, client: TestClient) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": ""},
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    def test_send_missing_content(self, client: TestClient) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            json={"sender": "test"},
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    def test_send_invalid_json(self, client: TestClient) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    def test_send_message_too_large(self, client: TestClient) -> None:
        # Default max is 64KB
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": "x" * 70000},
        )
        assert resp.status_code == 400
        assert "Message too large" in resp.json()["error"]

    def test_sender_length_capped(self, client: TestClient, store: MessageStore) -> None:
        long_sender = "x" * 200
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": "msg", "sender": long_sender},
        )
        assert resp.status_code == 201
        assert len(resp.json()["sender"]) == 128

    def test_sender_non_string_coerced(self, client: TestClient) -> None:
        resp = client.post(
            "/api/channels/test/messages",
            json={"content": "msg", "sender": 12345},
        )
        assert resp.status_code == 201
        assert resp.json()["sender"] == "12345"


class TestDebugClearAPI:
    """Tests for POST /api/channels/{channel}/clear."""

    def test_clear_existing(self, client: TestClient, store: MessageStore) -> None:
        store.add("test", "msg1")
        store.add("test", "msg2")

        resp = client.post("/api/channels/test/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "test"
        assert data["cleared"] is True

        # Verify the store is empty
        assert store.get("test") == []

    def test_clear_nonexistent(self, client: TestClient) -> None:
        resp = client.post("/api/channels/nonexistent/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] is False
