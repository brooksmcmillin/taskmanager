"""Tests for the debug REST API and web UI."""

from __future__ import annotations

import httpx
import pytest

from mcp_relay.debug import create_debug_app
from mcp_relay.server import MessageStore

TEST_TOKEN = "test-debug-token-12345"


@pytest.fixture
def store() -> MessageStore:
    return MessageStore()


@pytest.fixture
def client(store: MessageStore) -> httpx.AsyncClient:
    """Async client for the debug app *without* token auth."""
    app = create_debug_app(store)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
def auth_client(store: MessageStore) -> httpx.AsyncClient:
    """Async client for the debug app *with* token auth enabled."""
    app = create_debug_app(store, token=TEST_TOKEN)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class TestDebugAuth:
    """Tests for token authentication on the debug app."""

    @pytest.mark.asyncio
    async def test_rejects_missing_token(self, auth_client: httpx.AsyncClient) -> None:
        resp = await auth_client.get("/")
        assert resp.status_code == 401
        assert "Unauthorized" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_rejects_wrong_token(self, auth_client: httpx.AsyncClient) -> None:
        resp = await auth_client.get("/", headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_correct_token(self, auth_client: httpx.AsyncClient) -> None:
        resp = await auth_client.get("/", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200
        assert "MCP Relay Debug" in resp.text

    @pytest.mark.asyncio
    async def test_api_requires_token(self, auth_client: httpx.AsyncClient) -> None:
        resp = await auth_client.get("/api/channels")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_api_works_with_token(self, auth_client: httpx.AsyncClient) -> None:
        resp = await auth_client.get(
            "/api/channels",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"channels": []}

    @pytest.mark.asyncio
    async def test_no_token_config_allows_all(self, client: httpx.AsyncClient) -> None:
        """When no token is configured, all requests pass through."""
        resp = await client.get("/")
        assert resp.status_code == 200


class TestDebugIndex:
    """Tests for the HTML debug UI page."""

    @pytest.mark.asyncio
    async def test_returns_html(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "MCP Relay Debug" in resp.text

    @pytest.mark.asyncio
    async def test_contains_js(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/")
        assert "<script>" in resp.text
        assert "loadChannels" in resp.text


class TestDebugChannelsAPI:
    """Tests for GET /api/channels."""

    @pytest.mark.asyncio
    async def test_empty(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/channels")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"channels": []}

    @pytest.mark.asyncio
    async def test_with_data(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        await store.add("alpha", "msg1", "alice")
        await store.add("alpha", "msg2", "bob")
        await store.add("beta", "msg3", "carol")

        resp = await client.get("/api/channels")
        data = resp.json()
        assert len(data["channels"]) == 2

        by_name = {c["name"]: c for c in data["channels"]}
        assert by_name["alpha"]["message_count"] == 2
        assert by_name["beta"]["message_count"] == 1
        assert by_name["alpha"]["last_activity"] is not None
        assert by_name["beta"]["last_activity"] is not None


class TestDebugMessagesAPI:
    """Tests for GET /api/channels/{channel}/messages."""

    @pytest.mark.asyncio
    async def test_empty_channel(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/channels/nonexistent/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "nonexistent"
        assert data["messages"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_with_messages(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        await store.add("debug", "hello", "alice")
        await store.add("debug", "world", "bob")

        resp = await client.get("/api/channels/debug/messages")
        data = resp.json()
        assert data["channel"] == "debug"
        assert data["count"] == 2
        assert data["messages"][0]["content"] == "hello"
        assert data["messages"][0]["sender"] == "alice"
        assert data["messages"][1]["content"] == "world"
        assert data["messages"][1]["sender"] == "bob"

    @pytest.mark.asyncio
    async def test_since_filter(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        msg1 = await store.add("debug", "old")
        await store.add("debug", "new")

        resp = await client.get("/api/channels/debug/messages", params={"since": msg1.timestamp})
        data = resp.json()
        assert data["count"] == 1
        assert data["messages"][0]["content"] == "new"

    @pytest.mark.asyncio
    async def test_limit_parameter(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        for i in range(10):
            await store.add("debug", f"msg-{i}")

        resp = await client.get("/api/channels/debug/messages?limit=3")
        data = resp.json()
        assert data["count"] == 3
        # Should return the most recent 3 messages (no-cursor preserves original behavior)
        assert data["messages"][0]["content"] == "msg-7"
        assert data["messages"][2]["content"] == "msg-9"

    @pytest.mark.asyncio
    async def test_limit_zero_returns_default(
        self, client: httpx.AsyncClient, store: MessageStore
    ) -> None:
        for i in range(5):
            await store.add("debug", f"msg-{i}")

        resp = await client.get("/api/channels/debug/messages?limit=0")
        data = resp.json()
        # limit=0 should be treated as the default (100), returning all 5 messages
        assert data["count"] == 5

    @pytest.mark.asyncio
    async def test_invalid_limit(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/api/channels/debug/messages?limit=abc")
        assert resp.status_code == 400
        assert "Invalid limit" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_invalid_since(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        await store.add("test", "msg")
        resp = await client.get("/api/channels/test/messages?since=not-a-date")
        assert resp.status_code == 400
        assert "Invalid ISO timestamp" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_url_encoded_channel(
        self, client: httpx.AsyncClient, store: MessageStore
    ) -> None:
        await store.add("my-channel", "msg")
        resp = await client.get("/api/channels/my-channel/messages")
        data = resp.json()
        assert data["channel"] == "my-channel"
        assert data["count"] == 1


class TestDebugSendAPI:
    """Tests for POST /api/channels/{channel}/messages."""

    @pytest.mark.asyncio
    async def test_send_message(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        resp = await client.post(
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
        messages, _ = await store.get("test")
        assert len(messages) == 1
        assert messages[0].content == "hello from debug"

    @pytest.mark.asyncio
    async def test_send_default_sender(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/channels/test/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 201
        assert resp.json()["sender"] == "debug-ui"

    @pytest.mark.asyncio
    async def test_send_empty_content(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/channels/test/messages",
            json={"content": ""},
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_send_missing_content(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/channels/test/messages",
            json={"sender": "test"},
        )
        assert resp.status_code == 400
        assert "content is required" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_send_invalid_json(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/channels/test/messages",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert "Invalid JSON" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_send_message_too_large(self, client: httpx.AsyncClient) -> None:
        # Default max is 64KB
        resp = await client.post(
            "/api/channels/test/messages",
            json={"content": "x" * 70000},
        )
        assert resp.status_code == 400
        assert "Message too large" in resp.json()["error"]

    @pytest.mark.asyncio
    async def test_sender_length_capped(
        self, client: httpx.AsyncClient, store: MessageStore
    ) -> None:
        long_sender = "x" * 200
        resp = await client.post(
            "/api/channels/test/messages",
            json={"content": "msg", "sender": long_sender},
        )
        assert resp.status_code == 201
        assert len(resp.json()["sender"]) == 128

    @pytest.mark.asyncio
    async def test_sender_non_string_coerced(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            "/api/channels/test/messages",
            json={"content": "msg", "sender": 12345},
        )
        assert resp.status_code == 201
        assert resp.json()["sender"] == "12345"


class TestDebugClearAPI:
    """Tests for POST /api/channels/{channel}/clear."""

    @pytest.mark.asyncio
    async def test_clear_existing(self, client: httpx.AsyncClient, store: MessageStore) -> None:
        await store.add("test", "msg1")
        await store.add("test", "msg2")

        resp = await client.post("/api/channels/test/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "test"
        assert data["cleared"] is True

        # Verify the store is empty
        messages, _ = await store.get("test")
        assert messages == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/api/channels/nonexistent/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] is False
