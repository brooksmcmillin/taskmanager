"""Tests for CSRF protection middleware."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.csrf import CSRFMiddleware

ALLOWED_ORIGIN = "https://app.example.com"
EVIL_ORIGIN = "https://evil.example.com"


def _make_app(allowed_origins: list[str] | None = None) -> FastAPI:
    """Create a minimal FastAPI app with CSRFMiddleware."""
    mini_app = FastAPI()

    @mini_app.post("/action")
    async def action() -> dict[str, str]:
        return {"status": "ok"}

    @mini_app.get("/read")
    async def read() -> dict[str, str]:
        return {"status": "ok"}

    mini_app.add_middleware(
        CSRFMiddleware,
        allowed_origins=allowed_origins or [ALLOWED_ORIGIN],
    )
    return mini_app


def _session_cookie() -> dict[str, str]:
    """Return cookies dict with a fake session cookie."""
    return {"session": "fake-session-token"}


@pytest.mark.asyncio
async def test_safe_method_skips_csrf() -> None:
    """GET requests bypass CSRF checks entirely."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/read", cookies=_session_cookie())
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_origin_matches_allowed_origin() -> None:
    """POST with session cookie and allowed Origin passes."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"origin": ALLOWED_ORIGIN},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_origin_disallowed_returns_403() -> None:
    """POST with session cookie and disallowed Origin returns 403 CSRF_001."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"origin": EVIL_ORIGIN},
        )
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "CSRF_001"
    assert "origin not allowed" in detail["message"]


@pytest.mark.asyncio
async def test_referer_allowed_origin_passes() -> None:
    """POST with session cookie and allowed Referer passes."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"referer": f"{ALLOWED_ORIGIN}/some/page"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_referer_disallowed_origin_returns_403() -> None:
    """POST with session cookie and disallowed Referer returns 403."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"referer": f"{EVIL_ORIGIN}/phish"},
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CSRF_001"


@pytest.mark.asyncio
async def test_referer_malformed_returns_403() -> None:
    """POST with session cookie and malformed Referer returns 403."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"referer": "/relative-path-only"},
        )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CSRF_001"


@pytest.mark.asyncio
async def test_bearer_token_bypasses_csrf() -> None:
    """POST with Bearer token auth skips CSRF check even with session cookie."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={
                "authorization": "Bearer fake-token",
                "origin": EVIL_ORIGIN,
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_key_bypasses_csrf() -> None:
    """POST with x-api-key header skips CSRF check even with session cookie."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={
                "x-api-key": "some-api-key",
                "origin": EVIL_ORIGIN,
            },
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_no_session_cookie_bypasses_csrf() -> None:
    """POST without session cookie skips CSRF check even with evil origin."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            headers={"origin": EVIL_ORIGIN},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_no_origin_or_referer_passes() -> None:
    """POST with session cookie but no Origin/Referer passes (SameSite defense)."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_multiple_allowed_origins() -> None:
    """Middleware accepts any origin in the allowed list."""
    second_origin = "https://admin.example.com"
    app = _make_app(allowed_origins=[ALLOWED_ORIGIN, second_origin])
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp1 = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"origin": ALLOWED_ORIGIN},
        )
        resp2 = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={"origin": second_origin},
        )
    assert resp1.status_code == 200
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_origin_checked_before_referer() -> None:
    """When both Origin and Referer are present, Origin is used for validation."""
    app = _make_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Allowed origin + evil referer -> should pass (origin wins)
        response = await client.post(
            "/action",
            cookies=_session_cookie(),
            headers={
                "origin": ALLOWED_ORIGIN,
                "referer": f"{EVIL_ORIGIN}/page",
            },
        )
    assert response.status_code == 200
