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
        email="user1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
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
            "email": "user1@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
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
            "email": "user2@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
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
        email="user1_bulk@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
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
            "email": "user1_bulk@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
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
            "email": "user2_bulk@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
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


@pytest.mark.asyncio
async def test_cannot_create_nested_subtasks_via_post(
    authenticated_client: AsyncClient,
):
    """Test that POST /api/todos prevents creating subtasks of subtasks."""
    # Create parent
    parent = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent"},
    )
    parent_id = parent.json()["data"]["id"]

    # Create subtask
    subtask = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Subtask",
            "parent_id": parent_id,
        },
    )
    subtask_id = subtask.json()["data"]["id"]

    # Try to create a nested subtask directly (should fail)
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Nested Subtask",
            "parent_id": subtask_id,
        },
    )

    # Should fail with validation error
    assert response.status_code == 400
    assert "nesting" in response.json()["detail"]["message"].lower()


# Parent Task Link Tests


@pytest.mark.asyncio
async def test_get_subtask_includes_parent_task(authenticated_client: AsyncClient):
    """Test that getting a subtask includes parent_task details in the response."""
    # Create parent todo
    parent_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent Task", "priority": "high"},
    )
    parent_id = parent_response.json()["data"]["id"]

    # Create subtask
    subtask_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Child Task", "parent_id": parent_id},
    )
    subtask_id = subtask_response.json()["data"]["id"]

    # Get the subtask and verify parent_task is included
    response = await authenticated_client.get(f"/api/todos/{subtask_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parent_id"] == parent_id
    assert data["parent_task"] is not None
    assert data["parent_task"]["id"] == parent_id
    assert data["parent_task"]["title"] == "Parent Task"
    assert data["parent_task"]["priority"] == "high"
    assert data["parent_task"]["status"] == "pending"


@pytest.mark.asyncio
async def test_get_root_task_has_no_parent_task(authenticated_client: AsyncClient):
    """Test that a root-level task has parent_task as null."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Root Task"},
    )
    todo_id = response.json()["data"]["id"]

    response = await authenticated_client.get(f"/api/todos/{todo_id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parent_id"] is None
    assert data["parent_task"] is None


@pytest.mark.asyncio
async def test_get_subtask_does_not_leak_other_users_parent_task(
    client: AsyncClient,
    db_session,
):
    """Test that parent_task data is not returned if the parent belongs to another user.

    This is a security test (IDOR prevention): even if a subtask somehow references
    a parent owned by a different user, the API must not expose that parent's data.
    """
    from app.core.security import hash_password
    from app.models.todo import Todo
    from app.models.user import User

    # Create two users
    user1 = User(
        email="parent_owner@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="subtask_owner@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)

    # Create a task owned by user1
    user1_task = Todo(
        user_id=user1.id,
        title="User1 Secret Task",
        priority="high",
        status="pending",
        tags=[],
        position=0,
    )
    db_session.add(user1_task)
    await db_session.flush()
    await db_session.refresh(user1_task)

    # Create a task owned by user2 that references user1's task as parent
    # (simulating a data integrity issue or direct DB manipulation)
    user2_task = Todo(
        user_id=user2.id,
        title="User2 Task",
        priority="medium",
        status="pending",
        parent_id=user1_task.id,
        tags=[],
        position=0,
    )
    db_session.add(user2_task)
    await db_session.commit()
    await db_session.refresh(user2_task)

    # Login as user2
    login_response = await client.post(
        "/api/auth/login",
        json={
            "email": "subtask_owner@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
    )
    assert login_response.status_code == 200

    # parent_task must not be returned since parent belongs to user1
    response = await client.get(f"/api/todos/{user2_task.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parent_id"] == user1_task.id  # parent_id is still set
    assert data["parent_task"] is None  # but parent_task details must not be leaked


# Autonomy Tier Tests


@pytest.mark.asyncio
async def test_create_todo_with_valid_autonomy_tier(authenticated_client: AsyncClient):
    """Test creating a todo with a valid autonomy_tier value."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Research task",
            "autonomy_tier": 1,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["autonomy_tier"] == 1


@pytest.mark.asyncio
async def test_create_todo_autonomy_tier_min_boundary(
    authenticated_client: AsyncClient,
):
    """Test creating a todo with autonomy_tier at minimum boundary (1)."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Tier 1 task",
            "autonomy_tier": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["autonomy_tier"] == 1


@pytest.mark.asyncio
async def test_create_todo_autonomy_tier_max_boundary(
    authenticated_client: AsyncClient,
):
    """Test creating a todo with autonomy_tier at maximum boundary (4)."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Tier 4 task",
            "autonomy_tier": 4,
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["autonomy_tier"] == 4


@pytest.mark.asyncio
async def test_create_todo_rejects_autonomy_tier_below_minimum(
    authenticated_client: AsyncClient,
):
    """Test that autonomy_tier below 1 is rejected."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Invalid tier task",
            "autonomy_tier": 0,
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_todo_rejects_autonomy_tier_above_maximum(
    authenticated_client: AsyncClient,
):
    """Test that autonomy_tier above 4 is rejected."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Invalid tier task",
            "autonomy_tier": 5,
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_todo_infers_autonomy_tier_from_research_action(
    authenticated_client: AsyncClient,
):
    """Test that autonomy_tier is inferred from action_type='research' (tier 1)."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Research the new API",
            "description": "Look up documentation",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    # "research" keyword should infer action_type=research, autonomy_tier=1
    assert data["action_type"] == "research"
    assert data["autonomy_tier"] == 1


@pytest.mark.asyncio
async def test_create_todo_infers_autonomy_tier_from_code_action(
    authenticated_client: AsyncClient,
):
    """Test that autonomy_tier is inferred from action_type='code' (tier 3)."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Fix the login bug",
            "description": "Debug and fix the authentication issue",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    # "fix" and "bug" keywords should infer action_type=code, autonomy_tier=3
    assert data["action_type"] == "code"
    assert data["autonomy_tier"] == 3


@pytest.mark.asyncio
async def test_create_todo_infers_autonomy_tier_from_purchase_action(
    authenticated_client: AsyncClient,
):
    """Test that autonomy_tier is inferred from action_type='purchase' (tier 4)."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Buy new office supplies",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    # "buy" keyword should infer action_type=purchase, autonomy_tier=4
    assert data["action_type"] == "purchase"
    assert data["autonomy_tier"] == 4


@pytest.mark.asyncio
async def test_create_todo_explicit_autonomy_tier_overrides_inference(
    authenticated_client: AsyncClient,
):
    """Test that explicit autonomy_tier overrides the inferred value."""
    response = await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Research the new API",  # Would normally infer tier 1
            "autonomy_tier": 3,  # Explicit override
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    # Should use explicit tier 3, not inferred tier 1
    assert data["autonomy_tier"] == 3


@pytest.mark.asyncio
async def test_update_todo_autonomy_tier(authenticated_client: AsyncClient):
    """Test updating autonomy_tier on an existing todo."""
    # Create a todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Update the autonomy_tier
    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"autonomy_tier": 2},
    )

    assert response.status_code == 200
    assert response.json()["data"]["autonomy_tier"] == 2


@pytest.mark.asyncio
async def test_update_todo_rejects_invalid_autonomy_tier(
    authenticated_client: AsyncClient,
):
    """Test that updating with invalid autonomy_tier is rejected."""
    # Create a todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    # Try to update with invalid autonomy_tier
    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"autonomy_tier": 10},
    )

    assert response.status_code == 422  # Validation error


# Include Subtasks Tests


@pytest.mark.asyncio
async def test_list_todos_include_subtasks(authenticated_client: AsyncClient):
    """Test that include_subtasks=true returns subtasks with parent todos."""
    # Create parent todo
    parent = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent Task", "priority": "high"},
    )
    parent_id = parent.json()["data"]["id"]

    # Create subtasks
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Subtask 1", "parent_id": parent_id, "priority": "medium"},
    )
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Subtask 2", "parent_id": parent_id, "priority": "low"},
    )

    # List with include_subtasks=true
    response = await authenticated_client.get(
        "/api/todos",
        params={"include_subtasks": "true"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Should only return the parent (subtasks are not root-level)
    assert len(data) == 1
    assert data[0]["title"] == "Parent Task"

    # Subtasks should be nested under the parent
    assert len(data[0]["subtasks"]) == 2
    subtask_titles = {s["title"] for s in data[0]["subtasks"]}
    assert subtask_titles == {"Subtask 1", "Subtask 2"}


@pytest.mark.asyncio
async def test_list_todos_without_include_subtasks(authenticated_client: AsyncClient):
    """Test that without include_subtasks, subtasks array is empty."""
    # Create parent todo
    parent = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent Task"},
    )
    parent_id = parent.json()["data"]["id"]

    # Create subtask
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Subtask 1", "parent_id": parent_id},
    )

    # List without include_subtasks
    response = await authenticated_client.get("/api/todos")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["subtasks"] == []


@pytest.mark.asyncio
async def test_include_subtasks_does_not_leak_other_users_subtasks(
    client: AsyncClient,
    db_session,
):
    """Test that include_subtasks only returns subtasks owned by the requesting user.

    This is a BOLA/IDOR security test: if a user's todo happens to share an ID
    that another user's subtask references as parent_id, the subtask query must
    still only return subtasks belonging to the requesting user.
    """
    from app.core.security import hash_password
    from app.models.todo import Todo
    from app.models.user import User

    # Create two users
    user1 = User(
        email="subtask_user1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="subtask_user2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)

    # Create a parent task for user1
    user1_parent = Todo(
        user_id=user1.id,
        title="User1 Parent",
        priority="high",
        status="pending",
        tags=[],
        position=0,
    )
    db_session.add(user1_parent)
    await db_session.flush()
    await db_session.refresh(user1_parent)

    # Create a subtask for user1 under user1's parent
    user1_subtask = Todo(
        user_id=user1.id,
        title="User1 Secret Subtask",
        priority="medium",
        status="pending",
        parent_id=user1_parent.id,
        tags=[],
        position=0,
    )
    db_session.add(user1_subtask)

    # Create a parent task for user2
    user2_parent = Todo(
        user_id=user2.id,
        title="User2 Parent",
        priority="medium",
        status="pending",
        tags=[],
        position=0,
    )
    db_session.add(user2_parent)

    # Create a subtask owned by user2 that references user1's parent_id
    # (simulating direct DB manipulation or data integrity issue)
    user2_subtask_cross_ref = Todo(
        user_id=user2.id,
        title="User2 Subtask Referencing User1 Parent",
        priority="low",
        status="pending",
        parent_id=user1_parent.id,
        tags=[],
        position=1,
    )
    db_session.add(user2_subtask_cross_ref)
    await db_session.commit()

    # Login as user1 and request with include_subtasks
    login1 = await client.post(
        "/api/auth/login",
        json={
            "email": "subtask_user1@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
    )
    assert login1.status_code == 200

    response = await client.get(
        "/api/todos",
        params={"include_subtasks": "true"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    # Find user1's parent task
    parent_task = next((t for t in data if t["title"] == "User1 Parent"), None)
    assert parent_task is not None

    # Subtasks must only contain user1's subtask, NOT user2's cross-referenced subtask
    subtask_titles = [s["title"] for s in parent_task["subtasks"]]
    assert "User1 Secret Subtask" in subtask_titles
    assert "User2 Subtask Referencing User1 Parent" not in subtask_titles
    assert len(parent_task["subtasks"]) == 1


@pytest.mark.asyncio
async def test_include_subtasks_excludes_deleted_subtasks(
    authenticated_client: AsyncClient,
):
    """Test that deleted subtasks are not included even with include_subtasks=true."""
    # Create parent
    parent = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent Task"},
    )
    parent_id = parent.json()["data"]["id"]

    # Create two subtasks
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Subtask Keep", "parent_id": parent_id},
    )

    sub2 = await authenticated_client.post(
        "/api/todos",
        json={"title": "Subtask Delete", "parent_id": parent_id},
    )
    sub2_id = sub2.json()["data"]["id"]

    # Delete one subtask
    await authenticated_client.delete(f"/api/todos/{sub2_id}")

    # List with include_subtasks
    response = await authenticated_client.get(
        "/api/todos",
        params={"include_subtasks": "true"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    parent_data = next(t for t in data if t["title"] == "Parent Task")

    # Only the non-deleted subtask should appear
    assert len(parent_data["subtasks"]) == 1
    assert parent_data["subtasks"][0]["title"] == "Subtask Keep"


# =============================================================================
# updated_at Timestamp Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_todo_has_updated_at(authenticated_client: AsyncClient):
    """Test that newly created todos have updated_at populated."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Test Todo", "priority": "medium"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["updated_at"] is not None
    assert data["updated_at"] == data["created_at"]


@pytest.mark.asyncio
async def test_update_todo_preserves_updated_at(authenticated_client: AsyncClient):
    """Test that updated_at remains populated after updating a todo."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Original Title"},
    )
    todo_id = create_response.json()["data"]["id"]

    update_response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"title": "Updated Title"},
    )

    updated_data = update_response.json()["data"]
    assert updated_data["updated_at"] is not None


# =============================================================================
# Enum Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_todo_rejects_invalid_deadline_type(
    authenticated_client: AsyncClient,
):
    """Test that creating a todo with an invalid deadline_type is rejected."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Bad deadline", "deadline_type": "invalid_value"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_todo_accepts_valid_deadline_types(
    authenticated_client: AsyncClient,
):
    """Test that all valid DeadlineType enum values are accepted on create."""
    for deadline_type in ["flexible", "preferred", "firm", "hard"]:
        response = await authenticated_client.post(
            "/api/todos",
            json={
                "title": f"Task with {deadline_type}",
                "deadline_type": deadline_type,
            },
        )

        assert response.status_code == 201, f"Failed for deadline_type={deadline_type}"
        assert response.json()["data"]["deadline_type"] == deadline_type


@pytest.mark.asyncio
async def test_update_todo_rejects_invalid_deadline_type(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo with an invalid deadline_type is rejected."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"deadline_type": "not_a_real_type"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_todo_accepts_valid_deadline_type(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo with a valid deadline_type succeeds."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"deadline_type": "hard"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["deadline_type"] == "hard"


@pytest.mark.asyncio
async def test_create_todo_rejects_invalid_priority(
    authenticated_client: AsyncClient,
):
    """Test that creating a todo with an invalid priority is rejected."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Bad priority", "priority": "super_critical"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_todo_rejects_invalid_status(
    authenticated_client: AsyncClient,
):
    """Test that creating a todo with an invalid status is rejected."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Bad status", "status": "done"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_todo_rejects_invalid_action_type(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo with an invalid action_type is rejected."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"action_type": "teleport"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_todo_rejects_invalid_agent_status(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo with an invalid agent_status is rejected."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    todo_id = create_response.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"agent_status": "flying"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_todo_default_deadline_type_is_preferred(
    authenticated_client: AsyncClient,
):
    """Test that the default deadline_type is 'preferred' when not specified."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task without deadline_type"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["deadline_type"] == "preferred"


# Deadline Type Filtering and Sorting Tests


@pytest.mark.asyncio
async def test_create_todo_with_deadline_type(authenticated_client: AsyncClient):
    """Test creating a todo with an explicit deadline_type."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Hard deadline task", "deadline_type": "hard"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["deadline_type"] == "hard"


@pytest.mark.asyncio
async def test_update_todo_deadline_type(authenticated_client: AsyncClient):
    """Test updating a todo's deadline_type."""
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Change my deadline type"},
    )
    todo_id = create_response.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"deadline_type": "firm"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["deadline_type"] == "firm"


@pytest.mark.asyncio
async def test_filter_todos_invalid_deadline_type_returns_422(
    authenticated_client: AsyncClient,
):
    """Test that an invalid deadline_type returns 422."""
    response = await authenticated_client.get(
        "/api/todos", params={"deadline_type": "invalid_type"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_todos_invalid_order_by_returns_422(
    authenticated_client: AsyncClient,
):
    """Test that an invalid order_by returns 422."""
    response = await authenticated_client.get(
        "/api/todos", params={"order_by": "invalid_sort"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_todos_by_deadline_type(authenticated_client: AsyncClient):
    """Test filtering todos by deadline_type."""
    # Create todos with different deadline types
    for dt in ["flexible", "preferred", "firm", "hard"]:
        await authenticated_client.post(
            "/api/todos",
            json={"title": f"Task with {dt} deadline", "deadline_type": dt},
        )

    # Filter by "hard" only
    response = await authenticated_client.get(
        "/api/todos", params={"deadline_type": "hard"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] >= 1
    assert all(t["deadline_type"] == "hard" for t in data["data"])


@pytest.mark.asyncio
async def test_filter_todos_by_flexible_deadline_type(
    authenticated_client: AsyncClient,
):
    """Test filtering todos by flexible deadline_type."""
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Flexible task", "deadline_type": "flexible"},
    )
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Hard task", "deadline_type": "hard"},
    )

    response = await authenticated_client.get(
        "/api/todos", params={"deadline_type": "flexible"}
    )

    assert response.status_code == 200
    data = response.json()
    assert all(t["deadline_type"] == "flexible" for t in data["data"])


@pytest.mark.asyncio
async def test_sort_todos_by_deadline_type(authenticated_client: AsyncClient):
    """Test sorting by deadline_type (hard > firm > preferred > flexible)."""
    # Create todos with different deadline types and due dates
    for dt in ["flexible", "hard", "preferred", "firm"]:
        await authenticated_client.post(
            "/api/todos",
            json={
                "title": f"Sort test {dt}",
                "deadline_type": dt,
                "due_date": "2026-03-01",
            },
        )

    response = await authenticated_client.get(
        "/api/todos", params={"order_by": "deadline_type"}
    )

    assert response.status_code == 200
    data = response.json()
    deadline_types = [t["deadline_type"] for t in data["data"]]

    # Verify ordering: hard > firm > preferred > flexible
    type_order = {"hard": 3, "firm": 2, "preferred": 1, "flexible": 0}
    for i in range(len(deadline_types) - 1):
        assert type_order[deadline_types[i]] >= type_order[deadline_types[i + 1]]


@pytest.mark.asyncio
async def test_filter_deadline_type_with_other_filters(
    authenticated_client: AsyncClient,
):
    """Test that deadline_type filter works in combination with other filters."""
    # Create tasks with different combinations
    await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Hard pending",
            "deadline_type": "hard",
            "due_date": "2026-03-15",
        },
    )
    await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Flexible pending",
            "deadline_type": "flexible",
            "due_date": "2026-03-15",
        },
    )

    # Filter by deadline_type and date range
    response = await authenticated_client.get(
        "/api/todos",
        params={
            "deadline_type": "hard",
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert all(t["deadline_type"] == "hard" for t in data["data"])


@pytest.mark.asyncio
async def test_deadline_type_in_response(authenticated_client: AsyncClient):
    """Test that deadline_type is always included in todo responses."""
    for dt in ["flexible", "preferred", "firm", "hard"]:
        response = await authenticated_client.post(
            "/api/todos",
            json={"title": f"Response test {dt}", "deadline_type": dt},
        )
        assert response.json()["data"]["deadline_type"] == dt

    # Check list response includes deadline_type
    list_response = await authenticated_client.get("/api/todos")
    for todo in list_response.json()["data"]:
        assert "deadline_type" in todo


# --- Batch create tests ---


@pytest.mark.asyncio
async def test_batch_create_todos(authenticated_client: AsyncClient):
    """Test batch creation of multiple todos."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Batch task 1", "priority": "high"},
                {"title": "Batch task 2", "description": "Second task"},
                {"title": "Batch task 3", "priority": "low", "tags": ["test"]},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3
    assert len(data["data"]) == 3
    assert data["data"][0]["title"] == "Batch task 1"
    assert data["data"][1]["title"] == "Batch task 2"
    assert data["data"][2]["title"] == "Batch task 3"
    # Each should have a unique ID
    ids = [t["id"] for t in data["data"]]
    assert len(set(ids)) == 3


@pytest.mark.asyncio
async def test_batch_create_empty_list(authenticated_client: AsyncClient):
    """Test batch create rejects empty list."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={"todos": []},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_unauthenticated(client: AsyncClient):
    """Test batch create requires authentication."""
    response = await client.post(
        "/api/todos/batch",
        json={"todos": [{"title": "Task"}]},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_batch_create_with_subtasks(authenticated_client: AsyncClient):
    """Test batch create can create subtasks."""
    # Create a parent first
    parent_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Parent task"},
    )
    parent_id = parent_response.json()["data"]["id"]

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Subtask 1", "parent_id": parent_id},
                {"title": "Subtask 2", "parent_id": parent_id},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    for task in data["data"]:
        assert task["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_batch_create_atomic_rollback(authenticated_client: AsyncClient):
    """Test that batch create rolls back all todos if any validation fails.

    Items 1-2 are valid but item 3 references a nonexistent parent_id,
    so the entire batch should fail and no todos should be persisted.
    """
    # Confirm no todos exist initially
    list_response = await authenticated_client.get("/api/todos")
    assert list_response.json()["meta"]["count"] == 0

    # Attempt batch with invalid parent_id on the 3rd item
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Valid task 1"},
                {"title": "Valid task 2"},
                {"title": "Invalid task", "parent_id": 999999},
            ]
        },
    )

    assert response.status_code == 404

    # Verify no todos were persisted (atomicity)
    list_response = await authenticated_client.get("/api/todos")
    assert list_response.json()["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_batch_create_over_limit(authenticated_client: AsyncClient):
    """Test batch create rejects more than 50 todos."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={"todos": [{"title": f"Task {i}"} for i in range(51)]},
    )

    assert response.status_code == 422


# --- Batch create with parent_index tests ---


@pytest.mark.asyncio
async def test_batch_create_with_parent_index(authenticated_client: AsyncClient):
    """Test batch create with parent_index creates parent-child relationships."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Parent task"},
                {"title": "Child task 1", "parent_index": 0},
                {"title": "Child task 2", "parent_index": 0},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3

    parent_id = data["data"][0]["id"]
    assert data["data"][0]["parent_id"] is None
    assert data["data"][1]["parent_id"] == parent_id
    assert data["data"][2]["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_batch_create_parent_index_self_reference(
    authenticated_client: AsyncClient,
):
    """Test that parent_index cannot reference itself."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Self-parent", "parent_index": 0},
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_parent_index_out_of_range(
    authenticated_client: AsyncClient,
):
    """Test that parent_index out of range is rejected."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task 1"},
                {"title": "Task 2", "parent_index": 5},
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_parent_index_negative(authenticated_client: AsyncClient):
    """Test that negative parent_index is rejected."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task 1"},
                {"title": "Task 2", "parent_index": -1},
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_parent_index_forward_reference(
    authenticated_client: AsyncClient,
):
    """Test that parent_index cannot reference a later item."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Child first", "parent_index": 1},
                {"title": "Parent second"},
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_parent_index_nested_subtask(
    authenticated_client: AsyncClient,
):
    """Test that parent_index cannot point to a subtask (no multi-level)."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Grandparent"},
                {"title": "Parent", "parent_index": 0},
                {"title": "Child of child", "parent_index": 1},
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_parent_index_and_parent_id_conflict(
    authenticated_client: AsyncClient,
):
    """Test that parent_index and parent_id cannot both be set."""
    # Create a real parent task first
    parent_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Existing parent"},
    )
    parent_id = parent_response.json()["data"]["id"]

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Batch parent"},
                {
                    "title": "Conflicting child",
                    "parent_id": parent_id,
                    "parent_index": 0,
                },
            ]
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_batch_create_mixed_parent_id_and_parent_index(
    authenticated_client: AsyncClient,
):
    """Test mixing parent_id (existing task) and parent_index (batch task)."""
    # Create a real parent task first
    parent_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Existing parent"},
    )
    existing_parent_id = parent_response.json()["data"]["id"]

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Batch parent"},
                {"title": "Child of batch parent", "parent_index": 0},
                {"title": "Child of existing parent", "parent_id": existing_parent_id},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3

    batch_parent_id = data["data"][0]["id"]
    assert data["data"][0]["parent_id"] is None
    assert data["data"][1]["parent_id"] == batch_parent_id
    assert data["data"][2]["parent_id"] == existing_parent_id


@pytest.mark.asyncio
async def test_batch_create_parent_index_verifies_via_get(
    authenticated_client: AsyncClient,
):
    """Test that parent-child relationship from parent_index is reflected in GET."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Parent via batch"},
                {"title": "Subtask via batch", "parent_index": 0},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    parent_id = data["data"][0]["id"]

    # Fetch the parent and verify subtasks
    get_response = await authenticated_client.get(f"/api/todos/{parent_id}")
    assert get_response.status_code == 200
    parent_data = get_response.json()["data"]
    assert len(parent_data["subtasks"]) == 1
    assert parent_data["subtasks"][0]["title"] == "Subtask via batch"


@pytest.mark.asyncio
async def test_batch_create_parent_index_multiple_parents(
    authenticated_client: AsyncClient,
):
    """Test batch with multiple parent tasks and their children."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Parent A"},
                {"title": "Parent B"},
                {"title": "Child of A", "parent_index": 0},
                {"title": "Child of B", "parent_index": 1},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 4

    parent_a_id = data["data"][0]["id"]
    parent_b_id = data["data"][1]["id"]
    assert data["data"][2]["parent_id"] == parent_a_id
    assert data["data"][3]["parent_id"] == parent_b_id


# ---------------------------------------------------------------------------
# Batch create with wiki_page_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_create_with_wiki_page_id(authenticated_client: AsyncClient):
    """Batch creation with wiki_page_id links all tasks to the wiki page."""
    # Create a wiki page first
    wiki_resp = await authenticated_client.post(
        "/api/wiki", json={"title": "Audit Report", "content": "Full report"}
    )
    assert wiki_resp.status_code == 201
    wiki_page_id = wiki_resp.json()["data"]["id"]

    # Batch create tasks with wiki_page_id
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Finding 1"},
                {"title": "Finding 2"},
                {"title": "Finding 3"},
            ],
            "wiki_page_id": wiki_page_id,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3
    assert data["meta"]["wiki_page_id"] == wiki_page_id
    assert data["meta"]["wiki_links_created"] == 3

    # Verify all tasks are linked to the wiki page
    linked = await authenticated_client.get(f"/api/wiki/{wiki_page_id}/linked-tasks")
    assert linked.status_code == 200
    linked_ids = {t["id"] for t in linked.json()["data"]}
    created_ids = {t["id"] for t in data["data"]}
    assert linked_ids == created_ids


@pytest.mark.asyncio
async def test_batch_create_with_invalid_wiki_page_id(
    authenticated_client: AsyncClient,
):
    """Batch creation with nonexistent wiki_page_id returns 404."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [{"title": "Task 1"}],
            "wiki_page_id": 99999,
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_batch_create_without_wiki_page_id(authenticated_client: AsyncClient):
    """Batch creation without wiki_page_id still works (backward compat)."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "No wiki task 1"},
                {"title": "No wiki task 2"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    assert "wiki_page_id" not in data["meta"]
    assert "wiki_links_created" not in data["meta"]


@pytest.mark.asyncio
async def test_batch_create_wiki_page_id_null(authenticated_client: AsyncClient):
    """Batch creation with explicit null wiki_page_id works normally."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [{"title": "Null wiki task"}],
            "wiki_page_id": None,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 1
    assert "wiki_page_id" not in data["meta"]


@pytest.mark.asyncio
async def test_batch_create_with_estimated_hours(authenticated_client: AsyncClient):
    """Test batch creation persists estimated_hours on each todo."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task with estimate", "estimated_hours": 2.5},
                {"title": "Task without estimate"},
                {"title": "Task with zero estimate", "estimated_hours": 0},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3
    assert data["data"][0]["estimated_hours"] == 2.5
    assert data["data"][1]["estimated_hours"] is None
    assert data["data"][2]["estimated_hours"] == 0


# Category matching tests


@pytest.mark.asyncio
async def test_create_todo_with_exact_category_match(authenticated_client: AsyncClient):
    """Test creating a todo with a category that exactly matches an existing project."""
    # Create a project first
    project_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "ExactMatch Project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    # Create a todo using the exact category name
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task with exact category", "category": "ExactMatch Project"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["project_id"] == project_id
    assert data["project_name"] == "ExactMatch Project"


@pytest.mark.asyncio
async def test_create_todo_with_case_insensitive_category_match(
    authenticated_client: AsyncClient,
):
    """Test creating a todo with a category matching a project case-insensitively."""
    # Create a project with mixed case
    project_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Work Tasks"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    # Create todos using different casings
    for casing in ["work tasks", "WORK TASKS", "Work Tasks", "wOrK tAsKs"]:
        response = await authenticated_client.post(
            "/api/todos",
            json={"title": f"Task with casing '{casing}'", "category": casing},
        )
        assert response.status_code == 201, f"Failed for casing: {casing}"
        data = response.json()["data"]
        assert data["project_id"] == project_id, f"Wrong project for casing: {casing}"
        assert data["project_name"] == "Work Tasks", f"Wrong name for casing: {casing}"


@pytest.mark.asyncio
async def test_create_todo_with_nonexistent_category_auto_creates_project(
    authenticated_client: AsyncClient,
):
    """Test that a todo with a non-existent category auto-creates the project."""
    new_category = "Brand New Category"

    # Verify the project doesn't exist yet
    projects_before = await authenticated_client.get("/api/projects")
    project_names_before = [p["name"] for p in projects_before.json()["data"]]
    assert new_category not in project_names_before

    # Create a todo with a non-existent category
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task with new category", "category": new_category},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["project_name"] == new_category
    assert data["project_id"] is not None

    # Verify the project was auto-created
    projects_after = await authenticated_client.get("/api/projects")
    project_names_after = [p["name"] for p in projects_after.json()["data"]]
    assert new_category in project_names_after


@pytest.mark.asyncio
async def test_create_todo_without_category(authenticated_client: AsyncClient):
    """Test creating a todo without a category still works as before."""
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task without category"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["project_id"] is None
    assert data["project_name"] is None


@pytest.mark.asyncio
async def test_create_todo_nonexistent_category_reuses_created_project(
    authenticated_client: AsyncClient,
):
    """Test that subsequent tasks with the same category reuse the auto-created project.

    Verifies that auto-created projects are not duplicated on subsequent tasks.
    """
    new_category = "Auto Created Project"

    # Create two todos with the same new category
    response1 = await authenticated_client.post(
        "/api/todos",
        json={"title": "First task", "category": new_category},
    )
    response2 = await authenticated_client.post(
        "/api/todos",
        json={"title": "Second task", "category": new_category},
    )

    assert response1.status_code == 201
    assert response2.status_code == 201
    project_id_1 = response1.json()["data"]["project_id"]
    project_id_2 = response2.json()["data"]["project_id"]

    # Both tasks should be in the same project
    assert project_id_1 == project_id_2
    assert project_id_1 is not None


@pytest.mark.asyncio
async def test_batch_create_todos_with_nonexistent_category_auto_creates_project(
    authenticated_client: AsyncClient,
):
    """Test that batch creation with a non-existent category auto-creates the project.

    Ensures the auto-created project is shared by all tasks in the batch.
    """
    new_category = "Batch Auto Category"

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Batch task 1", "category": new_category},
                {"title": "Batch task 2", "category": new_category},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    project_id_1 = data["data"][0]["project_id"]
    project_id_2 = data["data"][1]["project_id"]
    assert project_id_1 is not None
    assert project_id_1 == project_id_2
    assert data["data"][0]["project_name"] == new_category


@pytest.mark.asyncio
async def test_batch_create_todos_with_case_insensitive_category_match(
    authenticated_client: AsyncClient,
):
    """Test that batch creation matches categories case-insensitively."""
    # Create a project first
    project_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Batch Project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Batch task 1", "category": "batch project"},
                {"title": "Batch task 2", "category": "BATCH PROJECT"},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    assert data["data"][0]["project_id"] == project_id
    assert data["data"][1]["project_id"] == project_id


@pytest.mark.asyncio
async def test_update_todo_with_nonexistent_category_auto_creates_project(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo with a non-existent category auto-creates it."""
    # Create a todo without a category
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    assert create_response.status_code == 201
    todo_id = create_response.json()["data"]["id"]

    new_category = "Update Auto Category"

    # Update the todo with a new category that doesn't exist
    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"category": new_category},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["project_name"] == new_category
    assert data["project_id"] is not None

    # Verify the project was auto-created
    projects = await authenticated_client.get("/api/projects")
    project_names = [p["name"] for p in projects.json()["data"]]
    assert new_category in project_names


@pytest.mark.asyncio
async def test_update_todo_with_case_insensitive_category_match(
    authenticated_client: AsyncClient,
):
    """Test that updating a todo matches categories case-insensitively."""
    # Create a project
    project_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Update Project"},
    )
    assert project_response.status_code == 201
    project_id = project_response.json()["data"]["id"]

    # Create a todo without a category
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task to update"},
    )
    assert create_response.status_code == 201
    todo_id = create_response.json()["data"]["id"]

    # Update the todo with a differently-cased category
    response = await authenticated_client.put(
        f"/api/todos/{todo_id}",
        json={"category": "update project"},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["project_id"] == project_id
    assert data["project_name"] == "Update Project"


@pytest.mark.asyncio
async def test_bulk_update_todos_with_nonexistent_category_auto_creates_project(
    authenticated_client: AsyncClient,
):
    """Test bulk update auto-creates a project for a non-existent category."""
    # Create two todos
    create1 = await authenticated_client.post(
        "/api/todos", json={"title": "Bulk task 1"}
    )
    create2 = await authenticated_client.post(
        "/api/todos", json={"title": "Bulk task 2"}
    )
    assert create1.status_code == 201
    assert create2.status_code == 201
    id1 = create1.json()["data"]["id"]
    id2 = create2.json()["data"]["id"]

    new_category = "Bulk Auto Category"

    # Bulk-update both todos with a new category
    response = await authenticated_client.put(
        "/api/todos",
        json={"ids": [id1, id2], "updates": {"category": new_category}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["updated"] == 2

    # Verify the project was auto-created
    projects = await authenticated_client.get("/api/projects")
    project_names_list = [p["name"] for p in projects.json()["data"]]
    assert new_category in project_names_list

    # Verify both todos now belong to the new project
    todo1 = await authenticated_client.get(f"/api/todos/{id1}")
    todo2 = await authenticated_client.get(f"/api/todos/{id2}")
    assert todo1.json()["data"]["project_name"] == new_category
    assert todo2.json()["data"]["project_name"] == new_category
    assert todo1.json()["data"]["project_id"] == todo2.json()["data"]["project_id"]


@pytest.mark.asyncio
async def test_create_todo_category_auto_create_fails_at_project_limit(
    authenticated_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Auto-creation is rejected when the user is at the project cap."""
    import app.api.todos as todos_module

    monkeypatch.setattr(todos_module, "_MAX_PROJECTS_PER_USER", 1)

    # Create exactly one project to hit the cap
    project_response = await authenticated_client.post(
        "/api/projects",
        json={"name": "Only Project"},
    )
    assert project_response.status_code == 201

    # Attempt to create a todo with a new category that would require auto-creation
    response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task", "category": "New Category Beyond Limit"},
    )

    assert response.status_code == 400
    assert "maximum" in response.json()["detail"]["message"].lower()


# ---------------------------------------------------------------------------
# Task deduplication tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_duplicate_todo_rejected(authenticated_client: AsyncClient):
    """Creating a todo with the same title as an active todo is rejected."""
    response1 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response1.status_code == 201

    response2 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response2.status_code == 409
    detail = response2.json()["detail"]
    assert detail["code"] == "CONFLICT_008"
    assert detail["details"]["existing_id"] == response1.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_duplicate_todo_case_insensitive(
    authenticated_client: AsyncClient,
):
    """Duplicate detection is case-insensitive and trims whitespace."""
    response1 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy Milk"}
    )
    assert response1.status_code == 201

    # Different case
    response2 = await authenticated_client.post(
        "/api/todos", json={"title": "buy milk"}
    )
    assert response2.status_code == 409

    # Extra whitespace
    response3 = await authenticated_client.post(
        "/api/todos", json={"title": "  Buy Milk  "}
    )
    assert response3.status_code == 409


@pytest.mark.asyncio
async def test_create_duplicate_allowed_after_completion(
    authenticated_client: AsyncClient,
):
    """Completing a todo allows creating another with the same title."""
    response1 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response1.status_code == 201
    todo_id = response1.json()["data"]["id"]

    # Complete the first todo
    await authenticated_client.patch(
        f"/api/todos/{todo_id}", json={"status": "completed"}
    )

    # Now the same title should be allowed
    response2 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response2.status_code == 201


@pytest.mark.asyncio
async def test_create_duplicate_allowed_after_cancellation(
    authenticated_client: AsyncClient,
):
    """Cancelling a todo allows creating another with the same title."""
    response1 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response1.status_code == 201
    todo_id = response1.json()["data"]["id"]

    await authenticated_client.patch(
        f"/api/todos/{todo_id}", json={"status": "cancelled"}
    )

    response2 = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk"}
    )
    assert response2.status_code == 201


@pytest.mark.asyncio
async def test_create_duplicate_different_descriptions_still_rejected(
    authenticated_client: AsyncClient,
):
    """Two todos with the same title but different descriptions are duplicates."""
    await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk", "description": "From store A"}
    )

    response = await authenticated_client.post(
        "/api/todos", json={"title": "Buy milk", "description": "From store B"}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_batch_create_rejects_duplicate_against_existing(
    authenticated_client: AsyncClient,
):
    """Batch creation rejects when a title matches an existing active todo."""
    await authenticated_client.post("/api/todos", json={"title": "Existing task"})

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "New task"},
                {"title": "Existing task"},
            ]
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONFLICT_008"


@pytest.mark.asyncio
async def test_batch_create_rejects_intra_batch_duplicate(
    authenticated_client: AsyncClient,
):
    """Batch creation rejects when two items in the same batch have the same title."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Same task"},
                {"title": "Same Task"},
            ]
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONFLICT_008"


@pytest.mark.asyncio
async def test_batch_create_skip_duplicates_against_existing(
    authenticated_client: AsyncClient,
):
    """With skip_duplicates=True, existing duplicates are silently skipped."""
    await authenticated_client.post("/api/todos", json={"title": "Existing task"})

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "skip_duplicates": True,
            "todos": [
                {"title": "New task"},
                {"title": "Existing task"},
                {"title": "Another new task"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    assert data["meta"]["skipped_duplicates"] == 1
    titles = [t["title"] for t in data["data"]]
    assert "New task" in titles
    assert "Another new task" in titles
    assert "Existing task" not in titles


@pytest.mark.asyncio
async def test_batch_create_skip_duplicates_intra_batch(
    authenticated_client: AsyncClient,
):
    """With skip_duplicates=True, intra-batch duplicates are silently skipped."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "skip_duplicates": True,
            "todos": [
                {"title": "Task A"},
                {"title": "Task B"},
                {"title": "task a"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2
    assert data["meta"]["skipped_duplicates"] == 1


@pytest.mark.asyncio
async def test_batch_create_skip_duplicates_all_skipped(
    authenticated_client: AsyncClient,
):
    """With skip_duplicates=True and all items duplicated, returns empty list."""
    await authenticated_client.post("/api/todos", json={"title": "Only task"})

    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "skip_duplicates": True,
            "todos": [
                {"title": "Only task"},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 0
    assert data["meta"]["skipped_duplicates"] == 1
