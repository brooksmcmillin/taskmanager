"""Tests for GET /api/categories endpoint."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User


@pytest.mark.asyncio
async def test_categories_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated request returns 401."""
    response = await client.get("/api/categories")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_categories_empty_state(authenticated_client: AsyncClient) -> None:
    """User with no projects gets an empty list."""
    response = await authenticated_client.get("/api/categories")

    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_categories_pending_count_excludes_completed(
    authenticated_client: AsyncClient,
) -> None:
    """Completed todos are excluded from pending_count."""
    # Create a project
    project_resp = await authenticated_client.post(
        "/api/projects",
        json={"name": "Count Test", "color": "#aabbcc"},
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["data"]["id"]

    # Create todos with different statuses
    await authenticated_client.post(
        "/api/todos",
        json={"title": "Pending task", "project_id": project_id, "status": "pending"},
    )
    await authenticated_client.post(
        "/api/todos",
        json={
            "title": "In-progress task",
            "project_id": project_id,
            "status": "in_progress",
        },
    )
    await authenticated_client.post(
        "/api/todos",
        json={
            "title": "Completed task",
            "project_id": project_id,
            "status": "completed",
        },
    )

    response = await authenticated_client.get("/api/categories")

    assert response.status_code == 200
    categories = response.json()["data"]
    assert len(categories) == 1
    cat = categories[0]
    assert cat["id"] == project_id
    assert cat["name"] == "Count Test"
    assert cat["color"] == "#aabbcc"
    # Only pending + in_progress count (completed excluded)
    assert cat["pending_count"] == 2


@pytest.mark.asyncio
async def test_categories_project_with_no_todos(
    authenticated_client: AsyncClient,
) -> None:
    """A project with no todos has pending_count of 0."""
    await authenticated_client.post(
        "/api/projects",
        json={"name": "Empty Project"},
    )

    response = await authenticated_client.get("/api/categories")

    assert response.status_code == 200
    categories = response.json()["data"]
    assert len(categories) == 1
    assert categories[0]["pending_count"] == 0


@pytest.mark.asyncio
async def test_categories_cross_user_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Other users' categories do not appear."""
    user1 = User(
        email="cat_user1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="cat_user2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1, create a project and a todo
    await client.post(
        "/api/auth/login",
        json={
            "email": "cat_user1@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
    )
    await client.post("/api/projects", json={"name": "User1 Project"})

    # Verify user1 sees their category
    resp1 = await client.get("/api/categories")
    assert resp1.status_code == 200
    assert resp1.json()["meta"]["count"] == 1
    assert resp1.json()["data"][0]["name"] == "User1 Project"

    await client.post("/api/auth/logout")

    # Login as user2
    await client.post(
        "/api/auth/login",
        json={
            "email": "cat_user2@example.com",
            "password": "TestPass123!",  # pragma: allowlist secret
        },
    )

    # user2 should see no categories
    resp2 = await client.get("/api/categories")
    assert resp2.status_code == 200
    assert resp2.json()["meta"]["count"] == 0
    assert resp2.json()["data"] == []


@pytest.mark.asyncio
async def test_categories_excludes_inactive_projects(
    authenticated_client: AsyncClient,
) -> None:
    """Deleted (inactive) projects do not appear in categories."""
    # Create then delete a project
    create_resp = await authenticated_client.post(
        "/api/projects",
        json={"name": "Will Delete"},
    )
    project_id = create_resp.json()["data"]["id"]
    await authenticated_client.delete(f"/api/projects/{project_id}")

    response = await authenticated_client.get("/api/categories")

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_categories_deleted_todos_excluded(
    authenticated_client: AsyncClient,
) -> None:
    """Soft-deleted todos are not counted in pending_count."""
    # Create a project and a todo
    project_resp = await authenticated_client.post(
        "/api/projects",
        json={"name": "Deletion Test"},
    )
    project_id = project_resp.json()["data"]["id"]

    todo_resp = await authenticated_client.post(
        "/api/todos",
        json={"title": "Will be deleted", "project_id": project_id},
    )
    todo_id = todo_resp.json()["data"]["id"]

    # Soft-delete the todo
    await authenticated_client.delete(f"/api/todos/{todo_id}")

    response = await authenticated_client.get("/api/categories")

    assert response.status_code == 200
    categories = response.json()["data"]
    assert len(categories) == 1
    assert categories[0]["pending_count"] == 0
