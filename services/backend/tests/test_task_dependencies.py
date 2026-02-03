"""Tests for task dependency endpoints."""

import pytest
from httpx import AsyncClient


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
