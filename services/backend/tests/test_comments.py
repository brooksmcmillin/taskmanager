"""Tests for task comment endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def test_todo(authenticated_client: AsyncClient) -> dict:
    """Create a test todo for comment tests."""
    response = await authenticated_client.post(
        "/api/todos", json={"title": "Test Todo with Comments"}
    )
    assert response.status_code == 201
    return response.json()["data"]


# =============================================================================
# Authentication Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_comments_requires_authentication(client: AsyncClient):
    """Test that listing comments requires authentication."""
    response = await client.get("/api/todos/1/comments")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_comment_requires_authentication(client: AsyncClient):
    """Test that creating comments requires authentication."""
    response = await client.post("/api/todos/1/comments", json={"content": "test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_comment_requires_authentication(client: AsyncClient):
    """Test that updating comments requires authentication."""
    response = await client.put("/api/todos/1/comments/1", json={"content": "test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_comment_requires_authentication(client: AsyncClient):
    """Test that deleting comments requires authentication."""
    response = await client.delete("/api/todos/1/comments/1")
    assert response.status_code == 401


# =============================================================================
# CRUD Operations Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_comments_empty(authenticated_client: AsyncClient, test_todo):
    """Test listing comments when there are none."""
    response = await authenticated_client.get(f"/api/todos/{test_todo['id']}/comments")
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_create_comment(authenticated_client: AsyncClient, test_todo):
    """Test creating a comment."""
    response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "This is a test comment"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["content"] == "This is a test comment"
    assert data["todo_id"] == test_todo["id"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_and_list_comments(authenticated_client: AsyncClient, test_todo):
    """Test creating multiple comments and listing them."""
    # Create two comments
    await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "First comment"},
    )
    await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "Second comment"},
    )

    # List
    response = await authenticated_client.get(f"/api/todos/{test_todo['id']}/comments")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 2
    assert data["meta"]["count"] == 2
    # Ordered by created_at asc
    assert data["data"][0]["content"] == "First comment"
    assert data["data"][1]["content"] == "Second comment"


@pytest.mark.asyncio
async def test_update_comment(authenticated_client: AsyncClient, test_todo):
    """Test updating a comment's content."""
    # Create
    create_response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "Original content"},
    )
    comment_id = create_response.json()["data"]["id"]

    # Update
    response = await authenticated_client.put(
        f"/api/todos/{test_todo['id']}/comments/{comment_id}",
        json={"content": "Updated content"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "Updated content"


@pytest.mark.asyncio
async def test_delete_comment(authenticated_client: AsyncClient, test_todo):
    """Test soft-deleting a comment."""
    # Create
    create_response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "To be deleted"},
    )
    comment_id = create_response.json()["data"]["id"]

    # Delete
    response = await authenticated_client.delete(
        f"/api/todos/{test_todo['id']}/comments/{comment_id}"
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["deleted"] is True
    assert data["id"] == comment_id


@pytest.mark.asyncio
async def test_deleted_comment_not_in_list(
    authenticated_client: AsyncClient, test_todo
):
    """Test that soft-deleted comments are filtered from list."""
    # Create two comments
    await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "Keep this"},
    )
    resp2 = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "Delete this"},
    )
    delete_id = resp2.json()["data"]["id"]

    # Delete one
    await authenticated_client.delete(
        f"/api/todos/{test_todo['id']}/comments/{delete_id}"
    )

    # List should only show the remaining one
    response = await authenticated_client.get(f"/api/todos/{test_todo['id']}/comments")
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["content"] == "Keep this"


# =============================================================================
# Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_comment_empty_content_rejected(
    authenticated_client: AsyncClient, test_todo
):
    """Test that empty content is rejected."""
    response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_comment_missing_content_rejected(
    authenticated_client: AsyncClient, test_todo
):
    """Test that missing content field is rejected."""
    response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={},
    )
    assert response.status_code == 422


# =============================================================================
# Not Found Tests
# =============================================================================


@pytest.mark.asyncio
async def test_create_comment_nonexistent_todo(authenticated_client: AsyncClient):
    """Test creating a comment on a nonexistent todo."""
    response = await authenticated_client.post(
        "/api/todos/99999/comments",
        json={"content": "orphan comment"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_nonexistent_comment(authenticated_client: AsyncClient, test_todo):
    """Test updating a nonexistent comment."""
    response = await authenticated_client.put(
        f"/api/todos/{test_todo['id']}/comments/99999",
        json={"content": "ghost"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_comment(authenticated_client: AsyncClient, test_todo):
    """Test deleting a nonexistent comment."""
    response = await authenticated_client.delete(
        f"/api/todos/{test_todo['id']}/comments/99999"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_already_deleted_comment(
    authenticated_client: AsyncClient, test_todo
):
    """Test that deleting an already-deleted comment returns 404."""
    # Create and delete
    create_response = await authenticated_client.post(
        f"/api/todos/{test_todo['id']}/comments",
        json={"content": "delete me twice"},
    )
    comment_id = create_response.json()["data"]["id"]
    await authenticated_client.delete(
        f"/api/todos/{test_todo['id']}/comments/{comment_id}"
    )

    # Try to delete again
    response = await authenticated_client.delete(
        f"/api/todos/{test_todo['id']}/comments/{comment_id}"
    )
    assert response.status_code == 404
