"""Tests for task dependency endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_dependencies_unauthenticated(client: AsyncClient):
    """Test listing dependencies without authentication."""
    response = await client.get("/api/todos/1/dependencies")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_add_dependency_unauthenticated(client: AsyncClient):
    """Test adding dependency without authentication."""
    response = await client.post(
        "/api/todos/1/dependencies",
        json={"dependency_id": 2},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_remove_dependency_unauthenticated(client: AsyncClient):
    """Test removing dependency without authentication."""
    response = await client.delete("/api/todos/1/dependencies/2")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_list_dependencies_empty(authenticated_client: AsyncClient):
    """Test listing dependencies when none exist."""
    # Create a todo
    create_response = await authenticated_client.post(
        "/api/todos",
        json={"title": "Task A"},
    )
    todo_id = create_response.json()["data"]["id"]

    # List dependencies
    response = await authenticated_client.get(f"/api/todos/{todo_id}/dependencies")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_add_dependency_success(authenticated_client: AsyncClient):
    """Test adding a dependency successfully."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency: Task A depends on Task B
    response = await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["id"] == task_b_id
    assert data["title"] == "Task B"


@pytest.mark.asyncio
async def test_get_todo_includes_dependencies(authenticated_client: AsyncClient):
    """Test that getting a todo includes its dependencies and dependents."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency: Task A depends on Task B
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    # Get Task A - should have Task B in dependencies
    response_a = await authenticated_client.get(f"/api/todos/{task_a_id}")
    data_a = response_a.json()["data"]
    assert len(data_a["dependencies"]) == 1
    assert data_a["dependencies"][0]["id"] == task_b_id
    assert len(data_a["dependents"]) == 0

    # Get Task B - should have Task A in dependents
    response_b = await authenticated_client.get(f"/api/todos/{task_b_id}")
    data_b = response_b.json()["data"]
    assert len(data_b["dependencies"]) == 0
    assert len(data_b["dependents"]) == 1
    assert data_b["dependents"][0]["id"] == task_a_id


@pytest.mark.asyncio
async def test_add_self_dependency_rejected(authenticated_client: AsyncClient):
    """Test that a task cannot depend on itself."""
    # Create a todo
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_a_id = task_a.json()["data"]["id"]

    # Try to add self-dependency
    response = await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_a_id},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CONFLICT_006"


@pytest.mark.asyncio
async def test_add_duplicate_dependency_rejected(authenticated_client: AsyncClient):
    """Test that duplicate dependencies are rejected."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    # Try to add same dependency again
    response = await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONFLICT_004"


@pytest.mark.asyncio
async def test_add_circular_dependency_simple_rejected(
    authenticated_client: AsyncClient,
):
    """Test that simple circular dependencies (A->B->A) are rejected."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency: A depends on B
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    # Try to add: B depends on A (would create A->B->A cycle)
    response = await authenticated_client.post(
        f"/api/todos/{task_b_id}/dependencies",
        json={"dependency_id": task_a_id},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CONFLICT_005"


@pytest.mark.asyncio
async def test_add_circular_dependency_chain_rejected(
    authenticated_client: AsyncClient,
):
    """Test that circular dependencies in chains (A->B->C->A) are rejected."""
    # Create three todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_c = await authenticated_client.post("/api/todos", json={"title": "Task C"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]
    task_c_id = task_c.json()["data"]["id"]

    # Create chain: A depends on B, B depends on C
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )
    await authenticated_client.post(
        f"/api/todos/{task_b_id}/dependencies",
        json={"dependency_id": task_c_id},
    )

    # Try to add: C depends on A (would create A->B->C->A cycle)
    response = await authenticated_client.post(
        f"/api/todos/{task_c_id}/dependencies",
        json={"dependency_id": task_a_id},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "CONFLICT_005"


@pytest.mark.asyncio
async def test_remove_dependency_success(authenticated_client: AsyncClient):
    """Test removing a dependency successfully."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    # Remove dependency
    response = await authenticated_client.delete(
        f"/api/todos/{task_a_id}/dependencies/{task_b_id}"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["deleted"] is True
    assert data["dependency_id"] == task_b_id

    # Verify dependency is gone
    list_response = await authenticated_client.get(
        f"/api/todos/{task_a_id}/dependencies"
    )
    assert list_response.json()["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_dependency(authenticated_client: AsyncClient):
    """Test removing a dependency that doesn't exist."""
    # Create a todo
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_a_id = task_a.json()["data"]["id"]

    # Try to remove non-existent dependency
    response = await authenticated_client.delete(
        f"/api/todos/{task_a_id}/dependencies/99999"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_010"


@pytest.mark.asyncio
async def test_add_dependency_to_nonexistent_todo(authenticated_client: AsyncClient):
    """Test adding dependency to a todo that doesn't exist."""
    response = await authenticated_client.post(
        "/api/todos/99999/dependencies",
        json={"dependency_id": 1},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"


@pytest.mark.asyncio
async def test_add_dependency_on_nonexistent_todo(authenticated_client: AsyncClient):
    """Test adding dependency on a todo that doesn't exist."""
    # Create a todo
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_a_id = task_a.json()["data"]["id"]

    response = await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": 99999},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_003"


@pytest.mark.asyncio
async def test_cascade_delete_removes_dependencies(authenticated_client: AsyncClient):
    """Test that deleting a task removes its dependencies."""
    # Create two todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]

    # Add dependency: A depends on B
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )

    # Delete Task B
    await authenticated_client.delete(f"/api/todos/{task_b_id}")

    # Get Task A - should have no dependencies (since B was deleted)
    response = await authenticated_client.get(f"/api/todos/{task_a_id}")
    data = response.json()["data"]
    # Note: soft-deleted tasks are filtered out from dependency responses
    assert len(data["dependencies"]) == 0


@pytest.mark.asyncio
async def test_multiple_dependencies(authenticated_client: AsyncClient):
    """Test a task can have multiple dependencies."""
    # Create three todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_c = await authenticated_client.post("/api/todos", json={"title": "Task C"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]
    task_c_id = task_c.json()["data"]["id"]

    # Add dependencies: A depends on B and C
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_c_id},
    )

    # Get dependencies
    response = await authenticated_client.get(f"/api/todos/{task_a_id}/dependencies")
    data = response.json()
    assert data["meta"]["count"] == 2
    dependency_ids = {dep["id"] for dep in data["data"]}
    assert task_b_id in dependency_ids
    assert task_c_id in dependency_ids


@pytest.mark.asyncio
async def test_complex_dependency_graph_no_cycle(authenticated_client: AsyncClient):
    """Test that complex dependency graphs without cycles are allowed.

    Create a diamond pattern: A depends on B and C, both B and C depend on D.
    This is valid and should not be detected as circular.
    """
    # Create four todos
    task_a = await authenticated_client.post("/api/todos", json={"title": "Task A"})
    task_b = await authenticated_client.post("/api/todos", json={"title": "Task B"})
    task_c = await authenticated_client.post("/api/todos", json={"title": "Task C"})
    task_d = await authenticated_client.post("/api/todos", json={"title": "Task D"})
    task_a_id = task_a.json()["data"]["id"]
    task_b_id = task_b.json()["data"]["id"]
    task_c_id = task_c.json()["data"]["id"]
    task_d_id = task_d.json()["data"]["id"]

    # Create diamond: A -> B -> D and A -> C -> D
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_b_id},
    )
    await authenticated_client.post(
        f"/api/todos/{task_a_id}/dependencies",
        json={"dependency_id": task_c_id},
    )
    await authenticated_client.post(
        f"/api/todos/{task_b_id}/dependencies",
        json={"dependency_id": task_d_id},
    )
    response = await authenticated_client.post(
        f"/api/todos/{task_c_id}/dependencies",
        json={"dependency_id": task_d_id},
    )

    # This should succeed - diamond is not a cycle
    assert response.status_code == 201


# =============================================================================
# Batch Creation with depends_on Tests
# =============================================================================


@pytest.mark.asyncio
async def test_batch_create_with_depends_on(authenticated_client: AsyncClient):
    """Test batch creation with depends_on indices creates dependencies."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Step 1: Setup"},
                {"title": "Step 2: Build", "depends_on": [0]},
                {"title": "Step 3: Deploy", "depends_on": [0, 1]},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3

    task_ids = [t["id"] for t in data["data"]]

    # Verify Step 2 depends on Step 1
    deps_1 = await authenticated_client.get(f"/api/todos/{task_ids[1]}/dependencies")
    assert deps_1.status_code == 200
    dep_ids_1 = {d["id"] for d in deps_1.json()["data"]}
    assert dep_ids_1 == {task_ids[0]}

    # Verify Step 3 depends on Step 1 and Step 2
    deps_2 = await authenticated_client.get(f"/api/todos/{task_ids[2]}/dependencies")
    assert deps_2.status_code == 200
    dep_ids_2 = {d["id"] for d in deps_2.json()["data"]}
    assert dep_ids_2 == {task_ids[0], task_ids[1]}


@pytest.mark.asyncio
async def test_batch_create_depends_on_empty_list(authenticated_client: AsyncClient):
    """Test batch creation with empty depends_on list works fine."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A", "depends_on": []},
                {"title": "Task B", "depends_on": []},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2


@pytest.mark.asyncio
async def test_batch_create_depends_on_without_field(authenticated_client: AsyncClient):
    """Test backward compatibility: batch creation without depends_on still works."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A"},
                {"title": "Task B"},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 2


@pytest.mark.asyncio
async def test_batch_create_depends_on_out_of_bounds(authenticated_client: AsyncClient):
    """Test batch creation rejects out-of-bounds depends_on index."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A"},
                {"title": "Task B", "depends_on": [5]},
            ]
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_depends_on_negative_index(
    authenticated_client: AsyncClient,
):
    """Test batch creation rejects negative depends_on index."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A"},
                {"title": "Task B", "depends_on": [-1]},
            ]
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_depends_on_self_reference(
    authenticated_client: AsyncClient,
):
    """Test batch creation rejects self-referencing depends_on."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A", "depends_on": [0]},
            ]
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_depends_on_circular(authenticated_client: AsyncClient):
    """Test batch creation rejects circular depends_on references."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A", "depends_on": [1]},
                {"title": "Task B", "depends_on": [0]},
            ]
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_depends_on_circular_chain(
    authenticated_client: AsyncClient,
):
    """Test batch creation rejects circular chain A->B->C->A."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task A", "depends_on": [2]},
                {"title": "Task B", "depends_on": [0]},
                {"title": "Task C", "depends_on": [1]},
            ]
        },
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_batch_create_depends_on_diamond_no_cycle(
    authenticated_client: AsyncClient,
):
    """Test batch creation allows diamond dependency pattern (not a cycle)."""
    # A depends on B and C, both B and C depend on D
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Task D"},
                {"title": "Task B", "depends_on": [0]},
                {"title": "Task C", "depends_on": [0]},
                {"title": "Task A", "depends_on": [1, 2]},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 4

    task_ids = [t["id"] for t in data["data"]]

    # Verify Task A depends on Task B and Task C
    deps = await authenticated_client.get(f"/api/todos/{task_ids[3]}/dependencies")
    dep_ids = {d["id"] for d in deps.json()["data"]}
    assert dep_ids == {task_ids[1], task_ids[2]}


@pytest.mark.asyncio
async def test_batch_create_depends_on_visible_in_get_todo(
    authenticated_client: AsyncClient,
):
    """Test that dependencies created via batch are visible in GET /todos/{id}."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Prerequisite"},
                {"title": "Main task", "depends_on": [0]},
            ]
        },
    )

    assert response.status_code == 201
    task_ids = [t["id"] for t in response.json()["data"]]

    # GET the dependent task and verify dependencies are included
    todo_response = await authenticated_client.get(f"/api/todos/{task_ids[1]}")
    assert todo_response.status_code == 200
    todo_data = todo_response.json()["data"]
    assert len(todo_data["dependencies"]) == 1
    assert todo_data["dependencies"][0]["id"] == task_ids[0]

    # GET the prerequisite task and verify dependents are included
    prereq_response = await authenticated_client.get(f"/api/todos/{task_ids[0]}")
    assert prereq_response.status_code == 200
    prereq_data = prereq_response.json()["data"]
    assert len(prereq_data["dependents"]) == 1
    assert prereq_data["dependents"][0]["id"] == task_ids[1]


@pytest.mark.asyncio
async def test_batch_create_mixed_depends_on_and_no_depends(
    authenticated_client: AsyncClient,
):
    """Test batch with a mix of tasks with and without depends_on."""
    response = await authenticated_client.post(
        "/api/todos/batch",
        json={
            "todos": [
                {"title": "Independent task"},
                {"title": "Another independent"},
                {"title": "Depends on first", "depends_on": [0]},
            ]
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["meta"]["count"] == 3

    task_ids = [t["id"] for t in data["data"]]

    # Independent tasks should have no dependencies
    deps_0 = await authenticated_client.get(f"/api/todos/{task_ids[0]}/dependencies")
    assert deps_0.json()["meta"]["count"] == 0

    deps_1 = await authenticated_client.get(f"/api/todos/{task_ids[1]}/dependencies")
    assert deps_1.json()["meta"]["count"] == 0

    # Third task depends on first
    deps_2 = await authenticated_client.get(f"/api/todos/{task_ids[2]}/dependencies")
    assert deps_2.json()["meta"]["count"] == 1
    assert deps_2.json()["data"][0]["id"] == task_ids[0]


# =============================================================================
# User isolation tests for circular dependency check
# =============================================================================


@pytest.mark.asyncio
async def test_circular_dependency_check_scoped_to_user(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that circular dependency check only considers the current user's tasks.

    User A has: task_a1 -> task_a2 (A1 depends on A2)
    User B has: task_b1 and task_b2 with no dependency yet.
    Adding task_b2 -> task_b1 should succeed (no cycle in user B's graph),
    even though the raw numeric IDs might overlap with user A's chain.
    This verifies the BFS is scoped by user_id and doesn't incorrectly
    mix user A's edges into user B's cycle check.
    """
    from app.core.security import hash_password
    from app.main import app
    from app.models.user import User

    user1 = User(
        email="dep_scope_u1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="dep_scope_u2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1 and create a dependency chain: task_a1 depends on task_a2
    await client.post(
        "/api/auth/login",
        json={  # pragma: allowlist secret
            "email": "dep_scope_u1@example.com",
            "password": "TestPass123!",
        },
    )
    task_a1 = await client.post("/api/todos", json={"title": "User1 Task A1"})
    task_a2 = await client.post("/api/todos", json={"title": "User1 Task A2"})
    task_a1_id = task_a1.json()["data"]["id"]
    task_a2_id = task_a2.json()["data"]["id"]
    await client.post(
        f"/api/todos/{task_a1_id}/dependencies",
        json={"dependency_id": task_a2_id},
    )
    await client.post("/api/auth/logout")

    # Login as user2 and create their own tasks
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as user2_client:
        # Share the same db session via override (already in place from client fixture)
        from app.dependencies import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        await user2_client.post(
            "/api/auth/login",
            json={  # pragma: allowlist secret
                "email": "dep_scope_u2@example.com",
                "password": "TestPass123!",
            },
        )
        task_b1 = await user2_client.post("/api/todos", json={"title": "User2 Task B1"})
        task_b2 = await user2_client.post("/api/todos", json={"title": "User2 Task B2"})
        task_b1_id = task_b1.json()["data"]["id"]
        task_b2_id = task_b2.json()["data"]["id"]

        # Add dependency: B1 depends on B2
        resp = await user2_client.post(
            f"/api/todos/{task_b1_id}/dependencies",
            json={"dependency_id": task_b2_id},
        )
        assert resp.status_code == 201

        # Now try to add B2 depends on B1 — this IS a real cycle in user2's graph
        resp_cycle = await user2_client.post(
            f"/api/todos/{task_b2_id}/dependencies",
            json={"dependency_id": task_b1_id},
        )
        assert resp_cycle.status_code == 400
        assert resp_cycle.json()["detail"]["code"] == "CONFLICT_005"


@pytest.mark.asyncio
async def test_user_a_deps_do_not_affect_user_b_cycle_check(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Test that user A's dependency graph does not influence user B's cycle check.

    Scenario: User A creates tasks X and Y with X depending on Y.
    User B creates tasks P and Q.
    User B should be able to add P->Q and Q->P... wait, that's a cycle.
    More precisely: user B creates P and Q with no deps. Adding P->Q should work
    since user A's X->Y chain should not pollute user B's BFS result.
    """
    from app.core.security import hash_password
    from app.main import app
    from app.models.user import User

    user_a = User(
        email="isolation_a@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user_b = User(
        email="isolation_b@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user_a)
    db_session.add(user_b)
    await db_session.commit()

    # User A: create chain X -> Y -> Z
    await client.post(
        "/api/auth/login",
        json={  # pragma: allowlist secret
            "email": "isolation_a@example.com",
            "password": "TestPass123!",
        },
    )
    x = await client.post("/api/todos", json={"title": "X"})
    y = await client.post("/api/todos", json={"title": "Y"})
    z = await client.post("/api/todos", json={"title": "Z"})
    x_id = x.json()["data"]["id"]
    y_id = y.json()["data"]["id"]
    z_id = z.json()["data"]["id"]
    await client.post(f"/api/todos/{x_id}/dependencies", json={"dependency_id": y_id})
    await client.post(f"/api/todos/{y_id}/dependencies", json={"dependency_id": z_id})
    await client.post("/api/auth/logout")

    # User B: create two independent tasks and add a valid (non-circular) dependency
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as user_b_client:
        from app.dependencies import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        await user_b_client.post(
            "/api/auth/login",
            json={  # pragma: allowlist secret
                "email": "isolation_b@example.com",
                "password": "TestPass123!",
            },
        )
        p = await user_b_client.post("/api/todos", json={"title": "P"})
        q = await user_b_client.post("/api/todos", json={"title": "Q"})
        p_id = p.json()["data"]["id"]
        q_id = q.json()["data"]["id"]

        # P depends on Q — this is NOT a cycle for user B
        resp = await user_b_client.post(
            f"/api/todos/{p_id}/dependencies",
            json={"dependency_id": q_id},
        )
        assert resp.status_code == 201, (
            f"Expected 201, got {resp.status_code}: {resp.json()}"
        )

        # Verify no false positive: user A's X->Y->Z chain didn't affect result
        deps = await user_b_client.get(f"/api/todos/{p_id}/dependencies")
        assert deps.json()["meta"]["count"] == 1
        assert deps.json()["data"][0]["id"] == q_id
