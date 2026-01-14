"""Tests for todo endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_todos_unauthenticated(client: AsyncClient):
    """Test listing todos without authentication."""
    response = await client.get("/api/todos")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_list_todos_empty(authenticated_client: AsyncClient):
    """Test listing todos when none exist."""
    response = await authenticated_client.get("/api/todos")

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_create_todo(authenticated_client: AsyncClient):
    """Test creating a todo."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Test Todo",
            "description": "A test task",
            "priority": "high",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["data"]["title"] == "Test Todo"
    assert "id" in data["data"]


@pytest.mark.asyncio
async def test_get_todo(authenticated_client: AsyncClient):
    """Test getting a specific todo."""
    # First create a todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Get Me"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Then get it
    response = await authenticated_client.get(f"/api/todos/{todo_id}")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_todo(authenticated_client: AsyncClient):
    """Test updating a todo."""
    # Create todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Update Me"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Update it
    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"title": "Updated Title", "priority": "urgent"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["updated"] is True


@pytest.mark.asyncio
async def test_complete_todo(authenticated_client: AsyncClient):
    """Test completing a todo."""
    # Create todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Complete Me"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Complete it
    response = await authenticated_client.post(f"/api/todos/{todo_id}/complete")

    assert response.status_code == 200
    assert response.json()["data"]["completed"] is True


@pytest.mark.asyncio
async def test_delete_todo(authenticated_client: AsyncClient):
    """Test deleting a todo (soft delete)."""
    # Create todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Delete Me"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Delete it
    response = await authenticated_client.delete(f"/api/todos/{todo_id}")

    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Verify it's no longer in the list
    list_response = await authenticated_client.get("/api/todos")
    assert all(t["id"] != todo_id for t in list_response.json()["tasks"])


@pytest.mark.asyncio
async def test_get_nonexistent_todo(authenticated_client: AsyncClient):
    """Test getting a todo that doesn't exist."""
    response = await authenticated_client.get("/api/todos/99999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"
