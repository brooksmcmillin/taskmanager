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
    assert data["data"] == []
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
    data = response.json()["data"]
    assert data["id"] == todo_id
    assert data["title"] == "Updated Title"
    assert data["priority"] == "urgent"


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
    assert all(t["id"] != todo_id for t in list_response.json()["data"])


@pytest.mark.asyncio
async def test_get_nonexistent_todo(authenticated_client: AsyncClient):
    """Test getting a todo that doesn't exist."""
    response = await authenticated_client.get("/api/todos/99999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"


# Subtask Security Tests


@pytest.mark.asyncio
async def test_cannot_update_subtask_to_other_users_parent(
    client: AsyncClient,
    db_session,
):
    """Test that a user cannot update their subtask to point to another user's todo.

    This is a security test to prevent users from attaching their subtasks to
    other users' todos by guessing parent IDs.
    """
    from app.core.security import hash_password
    from app.models.user import User

    # Create two users
    user1 = User(
        username="user1",
        email="user1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        username="user2",
        email="user2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1 and create a todo
    login1 = await client.post(
        "/api/auth/login",
        json={
            "username": "user1",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    assert login1.status_code == 200

    user1_todo = await client.post(
        "/api/todos",
        json={"title": "User 1's Todo"},
    )
    user1_todo_id = user1_todo.json()["data"]["id"]

    # Logout user1
    await client.post("/api/auth/logout")

    # Login as user2 and create their own todo and subtask
    login2 = await client.post(
        "/api/auth/login",
        json={
            "username": "user2",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    assert login2.status_code == 200

    user2_todo = await client.post(
        "/api/todos",
        json={"title": "User 2's Parent Todo"},
    )
    user2_todo_id = user2_todo.json()["data"]["id"]

    user2_subtask = await client.post(
        "/api/todos",
        json={
            "title": "User 2's Subtask",
            "parent_id": user2_todo_id,
        },
    )
    user2_subtask_id = user2_subtask.json()["data"]["id"]

    # Try to update user2's subtask to point to user1's todo (should fail)
    response = await client.put(
        f"/api/todos/{user2_subtask_id}",
        json={"parent_id": user1_todo_id},
    )

    # Should fail with 404 (parent not found because it belongs to user1)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"


@pytest.mark.asyncio
async def test_cannot_bulk_update_subtask_to_other_users_parent(
    client: AsyncClient,
    db_session,
):
    """Test that bulk update also prevents setting parent_id to another user's todo."""
    from app.core.security import hash_password
    from app.models.user import User

    # Create two users
    user1 = User(
        username="user1_bulk",
        email="user1_bulk@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        username="user2_bulk",
        email="user2_bulk@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1 and create a todo
    login1 = await client.post(
        "/api/auth/login",
        json={
            "username": "user1_bulk",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    assert login1.status_code == 200

    user1_todo = await client.post(
        "/api/todos",
        json={"title": "User 1's Todo for Bulk Test"},
    )
    user1_todo_id = user1_todo.json()["data"]["id"]

    # Logout user1
    await client.post("/api/auth/logout")

    # Login as user2 and create their own todos
    login2 = await client.post(
        "/api/auth/login",
        json={
            "username": "user2_bulk",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    assert login2.status_code == 200

    user2_subtask = await client.post(
        "/api/todos",
        json={"title": "User 2's Subtask for Bulk Test"},
    )
    user2_subtask_id = user2_subtask.json()["data"]["id"]

    # Try to bulk update to set parent_id to user1's todo (should fail)
    response = await client.put(
        "/api/todos",
        json={
            "ids": [user2_subtask_id],
            "updates": {"parent_id": user1_todo_id},
        },
    )

    # Should fail with 404
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"


@pytest.mark.asyncio
async def test_can_update_subtask_to_own_parent(authenticated_client: AsyncClient):
    """Test that a user CAN update their subtask to point to their own different parent.

    This is the happy path - users should be able to reorganize their own subtasks.
    """
    # Create two parent todos
    parent1 = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent 1"},
    )
    parent1_id = parent1.json()["data"]["id"]

    parent2 = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent 2"},
    )
    parent2_id = parent2.json()["data"]["id"]

    # Create subtask under parent1
    subtask = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "My Subtask",
            "parent_id": parent1_id,
        },
    )
    subtask_id = subtask.json()["data"]["id"]

    # Move subtask to parent2 (should succeed)
    response = await authenticated_client.put(
        f"/api/todos/{subtask_id}",
        json={"parent_id": parent2_id},
    )

    assert response.status_code == 200
    assert response.json()["data"]["parent_id"] == parent2_id


@pytest.mark.asyncio
async def test_cannot_create_nested_subtasks_via_update(
    authenticated_client: AsyncClient,
):
    """Test that updating parent_id prevents creating subtasks of subtasks."""
    # Create parent and subtask
    parent = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent"},
    )
    parent_id = parent.json()["data"]["id"]

    subtask = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Subtask",
            "parent_id": parent_id,
        },
    )
    subtask_id = subtask.json()["data"]["id"]

    # Create another todo and try to make it a subtask of the subtask
    another_todo = await authenticated_client.post(
        "/api/todos",
        json={"title": "Another Todo"},
    )
    another_todo_id = another_todo.json()["data"]["id"]

    # Try to set parent_id to the subtask (should fail)
    response = await authenticated_client.put(
        f"/api/todos/{another_todo_id}",
        json={"parent_id": subtask_id},
    )

    # Should fail with validation error
    assert response.status_code == 400
    assert "nesting" in response.json()["detail"]["message"].lower()
