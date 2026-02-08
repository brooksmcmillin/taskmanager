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


@pytest.mark.asyncio
async def test_list_projects_with_stats(authenticated_client: AsyncClient):
    """Test listing projects with statistics included."""
    # Create a project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Stats Test Project"},
    )
    project_id = create_response.json()["data"]["id"]

    # Create some tasks in the project
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Task 1", "project_id": project_id, "status": "completed"},
    )
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Task 2", "project_id": project_id, "status": "pending"},
    )
    await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Task 3",
            "project_id": project_id,
            "status": "in_progress",
            "estimated_hours": 5.0,
        },
    )

    # Get projects with stats
    response = await authenticated_client.get("/api/projects?include_stats=true")

    assert response.status_code == 200
    data = response.json()["data"]
    project = next(p for p in data if p["id"] == project_id)

    assert project["stats"] is not None
    stats = project["stats"]
    assert stats["total_tasks"] == 3
    assert stats["completed_tasks"] == 1
    assert stats["pending_tasks"] == 1
    assert stats["in_progress_tasks"] == 1
    assert stats["completion_percentage"] == pytest.approx(33.3, rel=0.1)
    assert stats["total_estimated_hours"] == 5.0


@pytest.mark.asyncio
async def test_get_project_stats_endpoint(authenticated_client: AsyncClient):
    """Test the dedicated project stats endpoint."""
    # Create a project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Dedicated Stats Test"},
    )
    project_id = create_response.json()["data"]["id"]

    # Create a completed task
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Done Task", "project_id": project_id, "status": "completed"},
    )

    # Get stats via dedicated endpoint
    response = await authenticated_client.get(f"/api/projects/{project_id}/stats")

    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats["total_tasks"] == 1
    assert stats["completed_tasks"] == 1
    assert stats["completion_percentage"] == 100.0


@pytest.mark.asyncio
async def test_project_stats_excludes_subtasks(authenticated_client: AsyncClient):
    """Test that project stats don't double-count subtasks."""
    # Create a project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Subtask Stats Test"},
    )
    project_id = create_response.json()["data"]["id"]

    # Create a parent task
    task_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent Task", "project_id": project_id},
    )
    parent_id = task_response.json()["data"]["id"]

    # Create a subtask
    await authenticated_client.post(
        f"/api/todos/{parent_id}/subtasks",
        json={"title": "Subtask 1"},
    )

    # Get stats - should only count the parent
    response = await authenticated_client.get(f"/api/projects/{project_id}/stats")

    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats["total_tasks"] == 1  # Only parent, not subtask


@pytest.mark.asyncio
async def test_project_stats_empty_project(authenticated_client: AsyncClient):
    """Test stats for a project with no tasks."""
    # Create a project
    create_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Empty Project"},
    )
    project_id = create_response.json()["data"]["id"]

    # Get stats
    response = await authenticated_client.get(f"/api/projects/{project_id}/stats")

    assert response.status_code == 200
    stats = response.json()["data"]
    assert stats["total_tasks"] == 0
    assert stats["completed_tasks"] == 0
    assert stats["completion_percentage"] == 0.0
    assert stats["total_estimated_hours"] is None
