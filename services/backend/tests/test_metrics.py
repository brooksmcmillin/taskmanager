"""Tests for the Prometheus /metrics endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_accessible(client: AsyncClient):
    """Test that /metrics endpoint is accessible without authentication."""
    response = await client.get("/metrics")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_metrics_returns_prometheus_format(client: AsyncClient):
    """Test that /metrics returns valid Prometheus text format."""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    # Prometheus exposition format includes HELP and TYPE lines
    assert "# HELP" in body
    assert "# TYPE" in body


@pytest.mark.asyncio
async def test_metrics_includes_http_metrics(client: AsyncClient):
    """Test that /metrics includes HTTP request metrics from the instrumentator."""
    # Make a request first so metrics are populated
    await client.get("/health")

    response = await client.get("/metrics")
    body = response.text

    # prometheus-fastapi-instrumentator exposes http_request_duration_seconds
    # and http_requests_total by default
    assert "http_request" in body


@pytest.mark.asyncio
async def test_metrics_excludes_health(client: AsyncClient):
    """Test that /health requests are excluded from instrumented metrics."""
    # Hit /health several times
    for _ in range(3):
        await client.get("/health")

    response = await client.get("/metrics")
    body = response.text

    # /health should be in excluded_handlers, so it should not appear
    # as a labeled handler in the metrics output
    for line in body.splitlines():
        if line.startswith("#"):
            continue
        if "handler" in line and "/health" in line:
            pytest.fail("/health should be excluded from instrumented metrics")
