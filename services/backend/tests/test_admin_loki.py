"""Tests for the Loki admin summary endpoint."""

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
        email="lokiadmin@example.com",
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
        json={"email": "lokiadmin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a non-admin test user."""
    user = User(
        email="lokiuser@example.com",
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
        json={"email": "lokiuser@example.com", "password": USER_PASSWORD},
    )
    assert response.status_code == 200
    return client


def _make_response(json_data: dict[str, object]) -> httpx.Response:
    """Create a real httpx.Response with the given JSON body."""
    import json

    return httpx.Response(
        status_code=200,
        content=json.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://loki:3100/mock"),
    )


def _mock_loki_responses() -> AsyncMock:
    """Create a mock httpx.AsyncClient that returns Loki-like responses."""
    mock_client = AsyncMock()

    async def mock_get(url: str, **_kwargs: object) -> httpx.Response:
        if url.endswith("/loki/api/v1/labels"):
            return _make_response(
                {
                    "status": "success",
                    "data": ["__name__", "container", "logstream", "host"],
                }
            )
        elif "/loki/api/v1/label/" in url and url.endswith("/values"):
            label = url.split("/loki/api/v1/label/")[1].split("/values")[0]
            if label == "container":
                return _make_response(
                    {
                        "status": "success",
                        "data": ["backend", "frontend", "postgres"],
                    }
                )
            elif label == "logstream":
                return _make_response(
                    {
                        "status": "success",
                        "data": ["stdout", "stderr"],
                    }
                )
            return _make_response({"status": "success", "data": []})
        elif url.endswith("/loki/api/v1/series"):
            return _make_response(
                {
                    "status": "success",
                    "data": [
                        {"container": "backend", "logstream": "stdout"},
                        {"container": "frontend", "logstream": "stdout"},
                    ],
                }
            )
        return _make_response({"status": "success", "data": []})

    mock_client.get = mock_get
    return mock_client


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Unauthenticated requests should get 401."""
    response = await client.get("/api/admin/loki/summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_returns_403(regular_client: AsyncClient) -> None:
    """Non-admin users should get 403."""
    response = await regular_client.get("/api/admin/loki/summary")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_gets_summary(admin_client: AsyncClient) -> None:
    """Admin users should get a successful Loki summary."""
    mock_client = _mock_loki_responses()

    with patch("app.api.admin_loki.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.get("/api/admin/loki/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert "container" in data["labels"]
    assert "logstream" in data["labels"]
    assert data["label_values"]["container"] == ["backend", "frontend", "postgres"]
    assert data["label_values"]["logstream"] == ["stdout", "stderr"]
    assert data["series_count"] == 2
    assert data["error"] is None


@pytest.mark.asyncio
async def test_loki_unreachable(admin_client: AsyncClient) -> None:
    """When Loki is unreachable, should return connected=False with error."""
    with patch("app.api.admin_loki.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.get("/api/admin/loki/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["labels"] == []
    assert data["label_values"] == {}
    assert data["series_count"] == 0
    assert data["error"] == "Unable to connect to Loki"


@pytest.mark.asyncio
async def test_loki_http_error(admin_client: AsyncClient) -> None:
    """When Loki returns an HTTP error, should return connected=False with error."""
    error_response = httpx.Response(
        status_code=500,
        content=b"Internal Server Error",
        request=httpx.Request("GET", "http://loki:3100/loki/api/v1/labels"),
    )
    with patch("app.api.admin_loki.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error", request=error_response.request, response=error_response
            )
        )
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        response = await admin_client.get("/api/admin/loki/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["error"] == "Loki returned an error response"
