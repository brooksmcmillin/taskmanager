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
            json={"title": f"Task with {deadline_type}", "deadline_type": deadline_type},
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
