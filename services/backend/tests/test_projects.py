"""Tests for project endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_projects_empty(authenticated_client: AsyncClient):
    """Test listing projects when none exist."""
    response = await authenticated_client.get("/api/projects")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_create_project(authenticated_client: AsyncClient):
    """Test creating a project."""
    response = await authenticated_client.post(
        "/api/projects",
        json={
            "name": "Test Project",
            "description": "A test project",
            "color": "#ff5733",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "Test Project"
    assert data["color"] == "#ff5733"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_update_project(authenticated_client: AsyncClient):
    """Test updating a project."""
    # Create project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Original Name"},
    )
    project_id = create_response.json()["data"]["id"]

    # Update it
    response = await authenticated_client.put(
        f"/api/projects/{project_id}",
        json={"name": "New Name", "color": "#00ff00"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "New Name"
    assert data["color"] == "#00ff00"


@pytest.mark.asyncio
async def test_delete_project(authenticated_client: AsyncClient):
    """Test deleting a project."""
    # Create project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Delete Me"},
    )
    project_id = create_response.json()["data"]["id"]

    # Delete it
    response = await authenticated_client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Verify it's gone
    get_response = await authenticated_client.get(f"/api/projects/{project_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_project(authenticated_client: AsyncClient):
    """Test getting a project that doesn't exist."""
    response = await authenticated_client.get("/api/projects/99999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_004"
