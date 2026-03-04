"""Tests for the MCP Relay admin proxy endpoints."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User

ADMIN_PASSWORD = "AdminPass123!"  # pragma: allowlist secret
USER_PASSWORD = "UserPass123!"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="relayadmin@example.com",
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Create an authenticated admin client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "relayadmin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a non-admin test user."""
    user = User(
        email="relayuser@example.com",
        password_hash=hash_password(USER_PASSWORD),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_client(client: AsyncClient, regular_user: User) -> AsyncClient:
    """Create an authenticated non-admin client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "relayuser@example.com", "password": USER_PASSWORD},
    )
    assert response.status_code == 200
    return client


def _make_response(
    json_data: dict,
    status_code: int = 200,
    method: str = "GET",
) -> httpx.Response:
    """Create a real httpx.Response with the given JSON body."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request(method, "http://mcp-relay:8002/debug/api/mock"),
    )


def _mock_relay_client(responses: dict[str, httpx.Response]) -> AsyncMock:
    """Create a mock httpx.AsyncClient that returns canned responses."""
    mock_client = AsyncMock()

    async def mock_get(url: str, **_kwargs: object) -> httpx.Response:
        for pattern, resp in responses.items():
            if pattern in url:
                return resp
        return _make_response({"error": "not found"}, status_code=404)

    async def mock_post(url: str, **_kwargs: object) -> httpx.Response:
        for pattern, resp in responses.items():
            if pattern in url:
                return resp
        return _make_response({"error": "not found"}, status_code=404)

    mock_client.get = mock_get
    mock_client.post = mock_post
    return mock_client


# ── Auth gating ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_channels_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/admin/relay/channels")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_channels_non_admin_returns_403(regular_client: AsyncClient) -> None:
    response = await regular_client.get("/api/admin/relay/channels")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_messages_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/admin/relay/channels/test/messages")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_messages_non_admin_returns_403(regular_client: AsyncClient) -> None:
    response = await regular_client.get("/api/admin/relay/channels/test/messages")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_send_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/admin/relay/channels/test/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_send_non_admin_returns_403(regular_client: AsyncClient) -> None:
    response = await regular_client.post(
        "/api/admin/relay/channels/test/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_clear_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.post("/api/admin/relay/channels/test/clear")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_clear_non_admin_returns_403(regular_client: AsyncClient) -> None:
    response = await regular_client.post("/api/admin/relay/channels/test/clear")
    assert response.status_code == 403


# ── Successful proxy ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_channels(admin_client: AsyncClient) -> None:
    relay_data = {
        "channels": [
            {
                "name": "test-ch",
                "message_count": 5,
                "last_activity": "2026-01-01T00:00:00Z",
            }
        ]
    }
    mock_client = _mock_relay_client(
        {"/debug/api/channels": _make_response(relay_data)}
    )

    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await admin_client.get("/api/admin/relay/channels")

    assert response.status_code == 200
    data = response.json()
    assert len(data["channels"]) == 1
    assert data["channels"][0]["name"] == "test-ch"


@pytest.mark.asyncio
async def test_get_messages(admin_client: AsyncClient) -> None:
    relay_data = {
        "channel": "test-ch",
        "messages": [
            {
                "id": "abc123",
                "content": "hello",
                "sender": "agent",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "count": 1,
    }
    mock_client = _mock_relay_client(
        {"/debug/api/channels/test-ch/messages": _make_response(relay_data)}
    )

    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await admin_client.get("/api/admin/relay/channels/test-ch/messages")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["messages"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_send_message(admin_client: AsyncClient) -> None:
    relay_data = {
        "id": "msg-1",
        "content": "test msg",
        "sender": "admin-ui",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    mock_client = _mock_relay_client(
        {
            "/debug/api/channels/test-ch/messages": _make_response(
                relay_data, status_code=201
            )
        }
    )

    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await admin_client.post(
            "/api/admin/relay/channels/test-ch/messages",
            json={"content": "test msg"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "test msg"


@pytest.mark.asyncio
async def test_invalid_channel_name_returns_400(admin_client: AsyncClient) -> None:
    """Channel names with invalid characters should be rejected."""
    # Spaces in channel name
    response = await admin_client.get("/api/admin/relay/channels/has%20spaces/messages")
    assert response.status_code == 400

    # Special characters
    response = await admin_client.post(
        "/api/admin/relay/channels/bad%40name/clear",
    )
    assert response.status_code == 400

    # Valid channel names should not be rejected
    # (will fail at relay level, but pass validation)
    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("not running"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await admin_client.post(
            "/api/admin/relay/channels/valid-channel_name.123/clear"
        )
    assert response.status_code == 200  # passes validation, fails at relay


@pytest.mark.asyncio
async def test_clear_channel(admin_client: AsyncClient) -> None:
    relay_data = {"channel": "test-ch", "cleared": True}
    mock_client = _mock_relay_client(
        {"/debug/api/channels/test-ch/clear": _make_response(relay_data)}
    )

    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        response = await admin_client.post("/api/admin/relay/channels/test-ch/clear")

    assert response.status_code == 200
    data = response.json()
    assert data["cleared"] is True


# ── Error handling ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_relay_unreachable_channels(admin_client: AsyncClient) -> None:
    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.get("/api/admin/relay/channels")

    assert response.status_code == 200
    data = response.json()
    assert data["channels"] == []
    assert data["error"] == "Unable to connect to MCP Relay"


@pytest.mark.asyncio
async def test_relay_timeout_messages(admin_client: AsyncClient) -> None:
    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.get("/api/admin/relay/channels/test/messages")

    assert response.status_code == 200
    data = response.json()
    assert data["messages"] == []
    assert data["error"] == "MCP Relay request timed out"


@pytest.mark.asyncio
async def test_relay_unreachable_send(admin_client: AsyncClient) -> None:
    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.post(
            "/api/admin/relay/channels/test/messages",
            json={"content": "hello"},
        )

    assert response.status_code == 502
    data = response.json()
    assert data["error"] == "Unable to connect to MCP Relay"


@pytest.mark.asyncio
async def test_relay_unreachable_clear(admin_client: AsyncClient) -> None:
    with patch("app.api.relay.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.post("/api/admin/relay/channels/test/clear")

    assert response.status_code == 200
    data = response.json()
    assert data["error"] == "Unable to connect to MCP Relay"
