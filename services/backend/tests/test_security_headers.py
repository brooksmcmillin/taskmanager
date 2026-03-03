"""Tests for HTTP security headers middleware."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security_headers import SecurityHeadersMiddleware

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "content-security-policy": "default-src 'none'",
    "permissions-policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
}


@pytest.mark.asyncio
async def test_security_headers_on_health(client: AsyncClient) -> None:
    """Security headers are present on a public endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    for header, expected_value in EXPECTED_HEADERS.items():
        assert response.headers.get(header) == expected_value, (
            f"Header {header!r} expected {expected_value!r}, "
            f"got {response.headers.get(header)!r}"
        )


@pytest.mark.asyncio
async def test_security_headers_on_404(client: AsyncClient) -> None:
    """Security headers are present even on 404 responses."""
    response = await client.get("/nonexistent-route")
    assert response.status_code == 404
    for header, expected_value in EXPECTED_HEADERS.items():
        assert response.headers.get(header) == expected_value, (
            f"Header {header!r} expected {expected_value!r}, "
            f"got {response.headers.get(header)!r}"
        )


@pytest.mark.asyncio
async def test_security_headers_on_post(client: AsyncClient) -> None:
    """Security headers are present on POST responses."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "wrong",  # pragma: allowlist secret
        },
    )
    # 401 or 400 depending on validation — either way headers should be set
    assert response.status_code in (400, 401, 422)
    for header, expected_value in EXPECTED_HEADERS.items():
        assert response.headers.get(header) == expected_value, (
            f"Header {header!r} expected {expected_value!r}, "
            f"got {response.headers.get(header)!r}"
        )


@pytest.mark.asyncio
async def test_hsts_not_set_in_development(client: AsyncClient) -> None:
    """Strict-Transport-Security is NOT set in non-production environments."""
    response = await client.get("/health")
    # The test environment is not production, so HSTS should be absent
    assert "strict-transport-security" not in response.headers


@pytest.mark.asyncio
async def test_hsts_set_in_production() -> None:
    """Strict-Transport-Security IS set when is_production=True.

    Uses a minimal standalone FastAPI app so there is no double-wrapping
    and no database dependency.
    """
    mini_app = FastAPI()

    @mini_app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    mini_app.add_middleware(SecurityHeadersMiddleware, is_production=True)

    async with AsyncClient(
        transport=ASGITransport(app=mini_app),
        base_url="http://test",
    ) as prod_client:
        response = await prod_client.get("/ping")

    assert response.headers.get("strict-transport-security") == (
        "max-age=31536000; includeSubDomains"
    )


@pytest.mark.asyncio
async def test_hsts_absent_in_development() -> None:
    """Strict-Transport-Security is absent when is_production=False."""
    mini_app = FastAPI()

    @mini_app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    mini_app.add_middleware(SecurityHeadersMiddleware, is_production=False)

    async with AsyncClient(
        transport=ASGITransport(app=mini_app),
        base_url="http://test",
    ) as dev_client:
        response = await dev_client.get("/ping")

    assert "strict-transport-security" not in response.headers
    # Other headers should still be present
    assert response.headers.get("x-content-type-options") == "nosniff"
