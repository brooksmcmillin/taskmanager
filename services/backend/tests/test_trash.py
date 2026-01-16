"""Tests for trash endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo
from app.models.user import User


@pytest.mark.asyncio
async def test_list_trash_unauthenticated(client: AsyncClient):
    """Test listing deleted todos without authentication."""
    response = await client.get("/api/trash")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_list_trash_empty(authenticated_client: AsyncClient):
    """Test listing trash when no deleted todos exist."""
    response = await authenticated_client.get("/api/trash")

    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
    assert data["count"] == 0


@pytest.mark.asyncio
async def test_list_trash_with_deleted_todos(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test listing trash with deleted todos."""
    # Create and soft delete a todo
    todo = Todo(
        user_id=test_user.id,
        title="Deleted Todo",
        description="This was deleted",
    )
    db_session.add(todo)
    await db_session.commit()
    await db_session.refresh(todo)

    # Soft delete it
    await authenticated_client.delete(f"/api/todos/{todo.id}")

    # List trash
    response = await authenticated_client.get("/api/trash")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == todo.id
    assert data["tasks"][0]["title"] == "Deleted Todo"
    assert data["tasks"][0]["deleted_at"] is not None


@pytest.mark.asyncio
async def test_list_trash_with_search_query(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test listing trash with search query filter."""
    # Create and delete multiple todos
    todo1 = Todo(user_id=test_user.id, title="Find me in trash")
    todo2 = Todo(user_id=test_user.id, title="Different task")
    db_session.add_all([todo1, todo2])
    await db_session.commit()

    # Delete both
    await authenticated_client.delete(f"/api/todos/{todo1.id}")
    await authenticated_client.delete(f"/api/todos/{todo2.id}")

    # Search for "Find"
    response = await authenticated_client.get("/api/trash?query=Find")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["tasks"][0]["title"] == "Find me in trash"


@pytest.mark.asyncio
async def test_restore_todo(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test restoring a deleted todo."""
    # Create and delete a todo
    todo = Todo(user_id=test_user.id, title="Restore Me")
    db_session.add(todo)
    await db_session.commit()
    await db_session.refresh(todo)

    await authenticated_client.delete(f"/api/todos/{todo.id}")

    # Verify it's in trash
    trash_response = await authenticated_client.get("/api/trash")
    assert trash_response.json()["count"] == 1

    # Restore it
    response = await authenticated_client.post(f"/api/trash/{todo.id}/restore")

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["restored"] is True
    assert data["data"]["id"] == todo.id

    # Verify it's no longer in trash
    trash_response = await authenticated_client.get("/api/trash")
    assert trash_response.json()["count"] == 0

    # Verify it's back in regular todos
    todos_response = await authenticated_client.get("/api/todos")
    assert todos_response.json()["meta"]["count"] == 1


@pytest.mark.asyncio
async def test_restore_todo_not_found(authenticated_client: AsyncClient):
    """Test restoring a todo that doesn't exist."""
    response = await authenticated_client.post("/api/trash/99999/restore")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_001"


@pytest.mark.asyncio
async def test_restore_todo_wrong_user(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test restoring a todo owned by another user."""
    # Create and delete a todo as test_user
    todo = Todo(user_id=test_user.id, title="Not Yours")
    db_session.add(todo)
    await db_session.commit()
    await db_session.refresh(todo)

    # Delete it
    from datetime import date

    todo.deleted_at = date.today()
    await db_session.commit()

    # Create another user
    from app.core.security import hash_password

    other_user = User(
        username="otheruser",
        email="other@example.com",
        password_hash=hash_password("OtherPass123!"),  # pragma: allowlist secret
    )
    db_session.add(other_user)
    await db_session.commit()

    # Login as other user
    response = await client.post(
        "/api/auth/login",
        json={
            "username": "otheruser",
            "password": "OtherPass123!",  # pragma: allowlist secret
        },
    )
    assert response.status_code == 200

    # Try to restore the first user's todo
    response = await client.post(f"/api/trash/{todo.id}/restore")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_001"
