"""Tests for the /health endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    """Test health check returns 200 with all subsystems healthy."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_response_shape(client: AsyncClient) -> None:
    """Test health check response contains all expected keys."""
    response = await client.get("/health")
    data = response.json()
    assert "status" in data
    assert "subsystems" in data
    assert "timestamp" in data

    expected_subsystems = {"tasks", "projects", "wiki", "snippets"}
    assert set(data["subsystems"].keys()) == expected_subsystems
    for name in expected_subsystems:
        assert data["subsystems"][name]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_503_when_db_unreachable(client: AsyncClient) -> None:
    """Test health check returns 503 when database connection fails."""
    from unittest.mock import AsyncMock

    from app.dependencies import get_db
    from app.main import app

    mock_session = AsyncMock()
    mock_session.execute.side_effect = ConnectionError("DB down")

    async def broken_db():
        yield mock_session

    app.dependency_overrides[get_db] = broken_db
    try:
        response = await client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["subsystems"] == {}
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_health_degraded_when_subsystem_fails(client: AsyncClient) -> None:
    """Test health check returns degraded when a subsystem probe fails."""
    from unittest.mock import AsyncMock, MagicMock

    from app.dependencies import get_db
    from app.main import app

    call_count = 0

    async def mock_execute(statement, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        # First call is SELECT 1 (connectivity check) - succeed
        if call_count == 1:
            return MagicMock()
        # Second call is tasks probe - fail
        if call_count == 2:
            raise Exception("simulated table failure")
        # All others succeed
        return MagicMock()

    mock_session = AsyncMock()
    mock_session.execute = mock_execute
    mock_session.rollback = AsyncMock()

    async def partial_db():
        yield mock_session

    app.dependency_overrides[get_db] = partial_db
    try:
        response = await client.get("/health")
        data = response.json()
        assert data["status"] == "degraded"
        assert data["subsystems"]["tasks"]["status"] == "unhealthy"
        # Other subsystems should still be healthy
        assert data["subsystems"]["projects"]["status"] == "healthy"
    finally:
        app.dependency_overrides.pop(get_db, None)
