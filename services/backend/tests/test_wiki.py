"""Tests for wiki page API endpoints."""

import pytest
from httpx import AsyncClient

from app.api.wiki import generate_slug

# ---------------------------------------------------------------------------
# Unit tests for slug generation
# ---------------------------------------------------------------------------


class TestGenerateSlug:
    def test_basic(self) -> None:
        assert generate_slug("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        assert generate_slug("Hello, World! #1") == "hello-world-1"

    def test_extra_spaces(self) -> None:
        assert generate_slug("  lots   of   spaces  ") == "lots-of-spaces"

    def test_unicode(self) -> None:
        # Non-ASCII word chars should pass through
        slug = generate_slug("café latte")
        assert slug == "café-latte"

    def test_empty_after_strip(self) -> None:
        assert generate_slug("!!!") == "untitled"

    def test_leading_trailing_hyphens(self) -> None:
        assert generate_slug("--hello--") == "hello"


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wiki_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/wiki")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_wiki_create_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/wiki", json={"title": "Test"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_page(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "My First Page", "content": "# Hello"}
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "My First Page"
    assert data["slug"] == "my-first-page"
    assert data["content"] == "# Hello"
    assert data["id"] > 0


@pytest.mark.asyncio
async def test_create_page_auto_slug(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Hello World!"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["slug"] == "hello-world"


@pytest.mark.asyncio
async def test_create_page_manual_slug(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Some Page", "slug": "custom-slug"}
    )
    assert response.status_code == 201
    assert response.json()["data"]["slug"] == "custom-slug"


@pytest.mark.asyncio
async def test_create_page_slug_dedup(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post("/api/wiki", json={"title": "Duplicate"})
    response = await authenticated_client.post("/api/wiki", json={"title": "Duplicate"})
    assert response.status_code == 201
    assert response.json()["data"]["slug"] == "duplicate-2"


@pytest.mark.asyncio
async def test_create_page_reserved_slug(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "New", "slug": "new"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_page_invalid_slug(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Bad Slug", "slug": "../admin"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_page_numeric_slug(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Numeric", "slug": "123"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_page_invalid_slug(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post("/api/wiki", json={"title": "Slug Val"})
    page_id = create.json()["data"]["id"]
    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"slug": "UPPER-CASE"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_page_reserved_slug_resolve(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Resolve", "slug": "resolve"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_pages(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post("/api/wiki", json={"title": "Page A"})
    await authenticated_client.post("/api/wiki", json={"title": "Page B"})

    response = await authenticated_client.get("/api/wiki")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_list_pages_search(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/wiki", json={"title": "Python Guide", "content": "about python"}
    )
    await authenticated_client.post(
        "/api/wiki", json={"title": "Rust Guide", "content": "about rust"}
    )

    response = await authenticated_client.get("/api/wiki", params={"q": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "Python Guide"


@pytest.mark.asyncio
async def test_get_page_by_id(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post("/api/wiki", json={"title": "By ID"})
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.get(f"/api/wiki/{page_id}")
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "By ID"


@pytest.mark.asyncio
async def test_get_page_by_slug(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post("/api/wiki", json={"title": "By Slug"})

    response = await authenticated_client.get("/api/wiki/by-slug")
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "By Slug"


@pytest.mark.asyncio
async def test_get_page_not_found(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/wiki/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_title(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post("/api/wiki", json={"title": "Original"})
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"title": "Updated Title"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Updated Title"
    assert data["slug"] == "updated-title"


@pytest.mark.asyncio
async def test_update_content(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Content Test"}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"content": "new content"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "new content"


@pytest.mark.asyncio
async def test_update_slug(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post("/api/wiki", json={"title": "Slug Test"})
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"slug": "custom"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["slug"] == "custom"


@pytest.mark.asyncio
async def test_delete_page(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post("/api/wiki", json={"title": "Delete Me"})
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.delete(f"/api/wiki/{page_id}")
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Should be gone
    get = await authenticated_client.get(f"/api/wiki/{page_id}")
    assert get.status_code == 404


# ---------------------------------------------------------------------------
# Resolve endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_titles(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post("/api/wiki", json={"title": "Alpha"})
    await authenticated_client.post("/api/wiki", json={"title": "Beta"})

    response = await authenticated_client.get(
        "/api/wiki/resolve", params={"titles": "Alpha,Beta,Missing"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["Alpha"] == "alpha"
    assert data["Beta"] == "beta"
    assert data["Missing"] is None


# ---------------------------------------------------------------------------
# Task linking tests
# ---------------------------------------------------------------------------


async def _create_todo(client: AsyncClient) -> int:
    """Helper to create a todo and return its ID."""
    response = await client.post("/api/todos", json={"title": "Test Task"})
    assert response.status_code == 201
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_link_task(authenticated_client: AsyncClient) -> None:
    page = await authenticated_client.post("/api/wiki", json={"title": "Linked"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    response = await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )
    assert response.status_code == 201
    assert response.json()["data"]["id"] == todo_id


@pytest.mark.asyncio
async def test_link_task_duplicate(authenticated_client: AsyncClient) -> None:
    page = await authenticated_client.post("/api/wiki", json={"title": "Dup Link"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )
    response = await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_linked_tasks(authenticated_client: AsyncClient) -> None:
    page = await authenticated_client.post("/api/wiki", json={"title": "Tasks Page"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )

    response = await authenticated_client.get(f"/api/wiki/{page_id}/linked-tasks")
    assert response.status_code == 200
    assert response.json()["meta"]["count"] == 1
    assert response.json()["data"][0]["id"] == todo_id


@pytest.mark.asyncio
async def test_unlink_task(authenticated_client: AsyncClient) -> None:
    page = await authenticated_client.post("/api/wiki", json={"title": "Unlink"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )
    response = await authenticated_client.delete(
        f"/api/wiki/{page_id}/link-task/{todo_id}"
    )
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Should have no more linked tasks
    tasks = await authenticated_client.get(f"/api/wiki/{page_id}/linked-tasks")
    assert tasks.json()["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_get_todo_wiki_pages(authenticated_client: AsyncClient) -> None:
    page = await authenticated_client.post("/api/wiki", json={"title": "Todo Wiki"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )

    response = await authenticated_client.get(f"/api/todos/{todo_id}/wiki-pages")
    assert response.status_code == 200
    assert response.json()["meta"]["count"] == 1
    assert response.json()["data"][0]["title"] == "Todo Wiki"


# ---------------------------------------------------------------------------
# Resolve oversized request test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_titles_too_many(authenticated_client: AsyncClient) -> None:
    titles = ",".join(f"Title{i}" for i in range(51))
    response = await authenticated_client.get(
        "/api/wiki/resolve", params={"titles": titles}
    )
    assert response.status_code == 400
    assert "Too many titles" in response.json()["detail"]["message"]


# ---------------------------------------------------------------------------
# Cross-user authorization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_read_other_users_page(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="wiki_a1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="wiki_a2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1 and create a page
    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_a1@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    create = await client.post("/api/wiki", json={"title": "Secret Page"})
    slug = create.json()["data"]["slug"]
    await client.post("/api/auth/logout")

    # Login as user2 and try to read user1's page
    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_a2@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    response = await client.get(f"/api/wiki/{slug}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_update_other_users_page(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="wiki_b1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="wiki_b2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_b1@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    create = await client.post("/api/wiki", json={"title": "Private Page"})
    page_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_b2@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    response = await client.put(f"/api/wiki/{page_id}", json={"title": "Hacked"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_other_users_page(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="wiki_c1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="wiki_c2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_c1@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    create = await client.post("/api/wiki", json={"title": "Delete Test"})
    page_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_c2@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    response = await client.delete(f"/api/wiki/{page_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_list_other_users_pages(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="wiki_d1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="wiki_d2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_d1@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    await client.post("/api/wiki", json={"title": "User1 Page"})
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_d2@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    response = await client.get("/api/wiki")
    assert response.status_code == 200
    assert response.json()["meta"]["count"] == 0
    assert response.json()["data"] == []


@pytest.mark.asyncio
async def test_cannot_link_task_to_other_users_page(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="wiki_e1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="wiki_e2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # User1 creates a wiki page
    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_e1@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    create = await client.post("/api/wiki", json={"title": "Link Target"})
    page_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    # User2 creates a task and tries to link it to user1's page
    await client.post(
        "/api/auth/login",
        json={
            "email": "wiki_e2@example.com",
            "password": "TestPass123!",
        },  # pragma: allowlist secret
    )
    todo = await client.post("/api/todos", json={"title": "User2 Task"})
    todo_id = todo.json()["data"]["id"]

    response = await client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )
    assert response.status_code == 404
