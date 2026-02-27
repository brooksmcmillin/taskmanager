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
    assert data["parent_id"] is None
    assert data["tags"] == []
    assert data["ancestors"] == []
    assert data["children"] == []


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
async def test_create_page_reserved_slug_tree(
    authenticated_client: AsyncClient,
) -> None:
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Tree", "slug": "tree"}
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


# ---------------------------------------------------------------------------
# Search content snippet tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_content_snippet(
    authenticated_client: AsyncClient,
) -> None:
    """Search results include a content snippet when a query matches content."""
    await authenticated_client.post(
        "/api/wiki",
        json={"title": "Generic Title", "content": "The quick brown fox jumps over"},
    )

    response = await authenticated_client.get("/api/wiki", params={"q": "brown fox"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    result = data["data"][0]
    assert "content_snippet" in result
    assert "brown fox" in result["content_snippet"]


@pytest.mark.asyncio
async def test_search_content_only_match(authenticated_client: AsyncClient) -> None:
    """A page whose title does NOT match but content DOES should be returned."""
    await authenticated_client.post(
        "/api/wiki",
        json={
            "title": "Unrelated Title",
            "content": "Some unique xylophone reference here",
        },
    )
    await authenticated_client.post(
        "/api/wiki",
        json={"title": "Another Page", "content": "Nothing special"},
    )

    response = await authenticated_client.get("/api/wiki", params={"q": "xylophone"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "Unrelated Title"
    assert "xylophone" in data["data"][0]["content_snippet"]


@pytest.mark.asyncio
async def test_list_without_search_no_snippet(
    authenticated_client: AsyncClient,
) -> None:
    """Listing without search query does not include a content snippet."""
    await authenticated_client.post("/api/wiki", json={"title": "No Search"})
    response = await authenticated_client.get("/api/wiki")
    assert response.status_code == 200
    result = response.json()["data"][0]
    # When not searching, content_snippet should be absent or None
    assert result.get("content_snippet") is None


# ---------------------------------------------------------------------------
# Append mode tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_append_mode(authenticated_client: AsyncClient) -> None:
    """When append=True, content is appended rather than replaced."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Append Test", "content": "Line 1"}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"content": "Line 2", "append": True}
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "Line 1\nLine 2"


@pytest.mark.asyncio
async def test_update_append_empty_content(authenticated_client: AsyncClient) -> None:
    """Appending to a page with empty content does not produce a leading newline."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Append Empty", "content": ""}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"content": "First line", "append": True}
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "First line"


@pytest.mark.asyncio
async def test_update_append_false_replaces(authenticated_client: AsyncClient) -> None:
    """When append=False (default), content replaces the old content."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Replace Test", "content": "Original"}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"content": "Replacement"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["content"] == "Replacement"


# ---------------------------------------------------------------------------
# Soft delete tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_page(authenticated_client: AsyncClient) -> None:
    """Deleting a page soft-deletes it (not visible in lists or gets)."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Soft Delete Me"}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.delete(f"/api/wiki/{page_id}")
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Should not appear in list
    listing = await authenticated_client.get("/api/wiki")
    assert all(p["id"] != page_id for p in listing.json()["data"])

    # Should not be fetchable by ID
    get_resp = await authenticated_client.get(f"/api/wiki/{page_id}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Revision history tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revision_created_on_update(authenticated_client: AsyncClient) -> None:
    """Updating a page creates a revision and increments revision_number."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Revisions", "content": "v1"}
    )
    page_id = create.json()["data"]["id"]
    assert create.json()["data"]["revision_number"] == 1

    # Update the page
    update = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"content": "v2"}
    )
    assert update.json()["data"]["revision_number"] == 2

    # Check revisions endpoint (list returns summaries without content)
    revisions = await authenticated_client.get(f"/api/wiki/{page_id}/revisions")
    assert revisions.status_code == 200
    rev_data = revisions.json()["data"]
    assert len(rev_data) == 1
    assert rev_data[0]["revision_number"] == 1
    assert "content" not in rev_data[0]

    # Full content is available via the specific revision endpoint
    rev_detail = await authenticated_client.get(f"/api/wiki/{page_id}/revisions/1")
    assert rev_detail.status_code == 200
    assert rev_detail.json()["data"]["content"] == "v1"


@pytest.mark.asyncio
async def test_get_specific_revision(authenticated_client: AsyncClient) -> None:
    """Can fetch a specific revision by number."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Rev Detail", "content": "first"}
    )
    page_id = create.json()["data"]["id"]

    await authenticated_client.put(f"/api/wiki/{page_id}", json={"content": "second"})
    await authenticated_client.put(f"/api/wiki/{page_id}", json={"content": "third"})

    # Get revision 1 (original state before first update)
    rev1 = await authenticated_client.get(f"/api/wiki/{page_id}/revisions/1")
    assert rev1.status_code == 200
    assert rev1.json()["data"]["content"] == "first"

    # Get revision 2 (state before second update)
    rev2 = await authenticated_client.get(f"/api/wiki/{page_id}/revisions/2")
    assert rev2.status_code == 200
    assert rev2.json()["data"]["content"] == "second"

    # Revision 3 doesn't exist yet (current state is rev 3)
    rev3 = await authenticated_client.get(f"/api/wiki/{page_id}/revisions/3")
    assert rev3.status_code == 404


@pytest.mark.asyncio
async def test_revisions_for_nonexistent_page(
    authenticated_client: AsyncClient,
) -> None:
    """Requesting revisions for a non-existent page returns 404."""
    response = await authenticated_client.get("/api/wiki/99999/revisions")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Batch link tasks tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_link_tasks(authenticated_client: AsyncClient) -> None:
    """Batch linking multiple tasks at once."""
    page = await authenticated_client.post("/api/wiki", json={"title": "Batch Link"})
    page_id = page.json()["data"]["id"]
    todo1_id = await _create_todo(authenticated_client)
    todo2_id = await _create_todo(authenticated_client)

    response = await authenticated_client.post(
        f"/api/wiki/{page_id}/link-tasks",
        json={"todo_ids": [todo1_id, todo2_id]},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data["linked"]) == {todo1_id, todo2_id}
    assert data["already_linked"] == []
    assert data["not_found"] == []


@pytest.mark.asyncio
async def test_batch_link_tasks_mixed(authenticated_client: AsyncClient) -> None:
    """Batch link with already-linked, new, and not-found IDs."""
    page = await authenticated_client.post("/api/wiki", json={"title": "Batch Mixed"})
    page_id = page.json()["data"]["id"]
    todo_id = await _create_todo(authenticated_client)

    # Link one task first
    await authenticated_client.post(
        f"/api/wiki/{page_id}/link-task", json={"todo_id": todo_id}
    )

    new_todo_id = await _create_todo(authenticated_client)

    response = await authenticated_client.post(
        f"/api/wiki/{page_id}/link-tasks",
        json={"todo_ids": [todo_id, new_todo_id, 99999]},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["linked"] == [new_todo_id]
    assert data["already_linked"] == [todo_id]
    assert data["not_found"] == [99999]


# ---------------------------------------------------------------------------
# Slug feedback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slug_modified_on_dedup(authenticated_client: AsyncClient) -> None:
    """When a slug is deduplicated, response indicates the modification."""
    await authenticated_client.post("/api/wiki", json={"title": "Slug Feedback"})
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Slug Feedback"}
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["slug"] == "slug-feedback-2"
    assert data["slug_modified"] is True
    assert data["requested_slug"] == "slug-feedback"


@pytest.mark.asyncio
async def test_slug_not_modified(authenticated_client: AsyncClient) -> None:
    """When slug is not modified, slug_modified is False."""
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Unique Page Title"}
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["slug_modified"] is False
    assert data["requested_slug"] is None


@pytest.mark.asyncio
async def test_slug_modified_on_update(authenticated_client: AsyncClient) -> None:
    """Slug modification feedback works on update too."""
    # Create two pages so the slug will conflict
    await authenticated_client.post(
        "/api/wiki", json={"title": "Taken Slug", "slug": "target-slug"}
    )
    create = await authenticated_client.post("/api/wiki", json={"title": "Other Page"})
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"slug": "target-slug"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["slug"] == "target-slug-2"
    assert data["slug_modified"] is True
    assert data["requested_slug"] == "target-slug"


# ---------------------------------------------------------------------------
# Hierarchy tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_parent(authenticated_client: AsyncClient) -> None:
    """Create a child page under a parent."""
    parent = await authenticated_client.post("/api/wiki", json={"title": "Parent Page"})
    parent_id = parent.json()["data"]["id"]

    child = await authenticated_client.post(
        "/api/wiki", json={"title": "Child Page", "parent_id": parent_id}
    )
    assert child.status_code == 201
    data = child.json()["data"]
    assert data["parent_id"] == parent_id
    assert len(data["ancestors"]) == 1
    assert data["ancestors"][0]["title"] == "Parent Page"


@pytest.mark.asyncio
async def test_depth_limit(authenticated_client: AsyncClient) -> None:
    """Cannot create pages beyond MAX_WIKI_DEPTH (3)."""
    p1 = await authenticated_client.post("/api/wiki", json={"title": "Level 1"})
    p1_id = p1.json()["data"]["id"]

    p2 = await authenticated_client.post(
        "/api/wiki", json={"title": "Level 2", "parent_id": p1_id}
    )
    p2_id = p2.json()["data"]["id"]

    p3 = await authenticated_client.post(
        "/api/wiki", json={"title": "Level 3", "parent_id": p2_id}
    )
    assert p3.status_code == 201
    p3_id = p3.json()["data"]["id"]

    # Level 4 should fail
    p4 = await authenticated_client.post(
        "/api/wiki", json={"title": "Level 4", "parent_id": p3_id}
    )
    assert p4.status_code == 400
    assert "depth" in p4.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_self_parent_rejected(authenticated_client: AsyncClient) -> None:
    """Cannot set a page as its own parent."""
    page = await authenticated_client.post("/api/wiki", json={"title": "Self Parent"})
    page_id = page.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"parent_id": page_id}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_circular_ref_prevented(authenticated_client: AsyncClient) -> None:
    """Cannot create circular parent references."""
    p1 = await authenticated_client.post("/api/wiki", json={"title": "Circ A"})
    p1_id = p1.json()["data"]["id"]

    p2 = await authenticated_client.post(
        "/api/wiki", json={"title": "Circ B", "parent_id": p1_id}
    )
    p2_id = p2.json()["data"]["id"]

    # Try to set p1's parent to p2 (p2 is a child of p1)
    response = await authenticated_client.put(
        f"/api/wiki/{p1_id}", json={"parent_id": p2_id}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cascade_soft_delete(authenticated_client: AsyncClient) -> None:
    """Deleting a parent soft-deletes its children."""
    parent = await authenticated_client.post("/api/wiki", json={"title": "Parent Del"})
    parent_id = parent.json()["data"]["id"]

    child = await authenticated_client.post(
        "/api/wiki", json={"title": "Child Del", "parent_id": parent_id}
    )
    child_id = child.json()["data"]["id"]

    # Delete parent
    response = await authenticated_client.delete(f"/api/wiki/{parent_id}")
    assert response.status_code == 200

    # Child should also be gone
    child_get = await authenticated_client.get(f"/api/wiki/{child_id}")
    assert child_get.status_code == 404


@pytest.mark.asyncio
async def test_ancestors_in_response(authenticated_client: AsyncClient) -> None:
    """Getting a page returns its ancestor chain."""
    root = await authenticated_client.post("/api/wiki", json={"title": "Root"})
    root_id = root.json()["data"]["id"]

    mid = await authenticated_client.post(
        "/api/wiki", json={"title": "Mid", "parent_id": root_id}
    )
    mid_id = mid.json()["data"]["id"]

    leaf = await authenticated_client.post(
        "/api/wiki", json={"title": "Leaf", "parent_id": mid_id}
    )
    leaf_slug = leaf.json()["data"]["slug"]

    response = await authenticated_client.get(f"/api/wiki/{leaf_slug}")
    data = response.json()["data"]
    assert len(data["ancestors"]) == 2
    assert data["ancestors"][0]["title"] == "Root"
    assert data["ancestors"][1]["title"] == "Mid"


@pytest.mark.asyncio
async def test_children_in_response(authenticated_client: AsyncClient) -> None:
    """Getting a page returns its direct children with counts."""
    parent = await authenticated_client.post("/api/wiki", json={"title": "P"})
    parent_id = parent.json()["data"]["id"]

    child = await authenticated_client.post(
        "/api/wiki", json={"title": "C1", "parent_id": parent_id}
    )
    child_id = child.json()["data"]["id"]

    # Add grandchild under child
    await authenticated_client.post(
        "/api/wiki", json={"title": "GC1", "parent_id": child_id}
    )

    response = await authenticated_client.get(f"/api/wiki/{parent_id}")
    data = response.json()["data"]
    assert len(data["children"]) == 1
    assert data["children"][0]["title"] == "C1"
    assert data["children"][0]["child_count"] == 1


@pytest.mark.asyncio
async def test_tree_endpoint(authenticated_client: AsyncClient) -> None:
    """The tree endpoint returns nested structure."""
    root = await authenticated_client.post("/api/wiki", json={"title": "Tree Root"})
    root_id = root.json()["data"]["id"]

    await authenticated_client.post(
        "/api/wiki", json={"title": "Tree Child", "parent_id": root_id}
    )
    await authenticated_client.post("/api/wiki", json={"title": "Orphan"})

    response = await authenticated_client.get("/api/wiki/tree")
    assert response.status_code == 200
    data = response.json()["data"]
    # Should have 2 root nodes
    titles = [n["title"] for n in data]
    assert "Orphan" in titles
    assert "Tree Root" in titles
    root_node = next(n for n in data if n["title"] == "Tree Root")
    assert len(root_node["children"]) == 1
    assert root_node["children"][0]["title"] == "Tree Child"


@pytest.mark.asyncio
async def test_reparenting(authenticated_client: AsyncClient) -> None:
    """Can move a page to a different parent."""
    p1 = await authenticated_client.post("/api/wiki", json={"title": "Parent A"})
    p1_id = p1.json()["data"]["id"]

    p2 = await authenticated_client.post("/api/wiki", json={"title": "Parent B"})
    p2_id = p2.json()["data"]["id"]

    child = await authenticated_client.post(
        "/api/wiki", json={"title": "Moving Child", "parent_id": p1_id}
    )
    child_id = child.json()["data"]["id"]

    # Move child to p2
    response = await authenticated_client.put(
        f"/api/wiki/{child_id}", json={"parent_id": p2_id}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["parent_id"] == p2_id
    assert data["ancestors"][0]["title"] == "Parent B"


@pytest.mark.asyncio
async def test_reparenting_subtree_depth_violation(
    authenticated_client: AsyncClient,
) -> None:
    """Moving a page with descendants cannot exceed MAX_WIKI_DEPTH."""
    # Build chain: Root_A -> Child_A -> Grandchild_A (depth 3)
    root_a = await authenticated_client.post(
        "/api/wiki", json={"title": "DepthA Root"}
    )
    root_a_id = root_a.json()["data"]["id"]

    child_a = await authenticated_client.post(
        "/api/wiki", json={"title": "DepthA Child", "parent_id": root_a_id}
    )
    child_a_id = child_a.json()["data"]["id"]

    await authenticated_client.post(
        "/api/wiki", json={"title": "DepthA Grand", "parent_id": child_a_id}
    )

    # Build: Root_B -> Child_B (depth 2)
    root_b = await authenticated_client.post(
        "/api/wiki", json={"title": "DepthB Root"}
    )
    root_b_id = root_b.json()["data"]["id"]

    child_b = await authenticated_client.post(
        "/api/wiki", json={"title": "DepthB Child", "parent_id": root_b_id}
    )
    child_b_id = child_b.json()["data"]["id"]

    # Moving Root_A (which has 2 levels below) under Child_B (depth 2)
    # would put Root_A at depth 3, Child_A at 4, Grandchild_A at 5 => reject
    response = await authenticated_client.put(
        f"/api/wiki/{root_a_id}", json={"parent_id": child_b_id}
    )
    assert response.status_code == 400
    assert "depth" in response.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_remove_parent(authenticated_client: AsyncClient) -> None:
    """Can remove a page's parent to make it a root page."""
    parent = await authenticated_client.post(
        "/api/wiki", json={"title": "Remove Parent Test"}
    )
    parent_id = parent.json()["data"]["id"]

    child = await authenticated_client.post(
        "/api/wiki", json={"title": "Becomes Root", "parent_id": parent_id}
    )
    child_id = child.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{child_id}", json={"remove_parent": True}
    )
    assert response.status_code == 200
    assert response.json()["data"]["parent_id"] is None
    assert response.json()["data"]["ancestors"] == []


@pytest.mark.asyncio
async def test_parent_not_found(authenticated_client: AsyncClient) -> None:
    """Cannot set a non-existent page as parent."""
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Bad Parent", "parent_id": 99999}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_filter_by_parent_root(authenticated_client: AsyncClient) -> None:
    """Filtering with parent_id=0 returns only root pages."""
    root = await authenticated_client.post("/api/wiki", json={"title": "Root Only"})
    root_id = root.json()["data"]["id"]

    await authenticated_client.post(
        "/api/wiki", json={"title": "Child Only", "parent_id": root_id}
    )

    response = await authenticated_client.get("/api/wiki", params={"parent_id": 0})
    assert response.status_code == 200
    titles = [p["title"] for p in response.json()["data"]]
    assert "Root Only" in titles
    assert "Child Only" not in titles


# ---------------------------------------------------------------------------
# Tag tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_tags(authenticated_client: AsyncClient) -> None:
    """Create a page with tags."""
    response = await authenticated_client.post(
        "/api/wiki", json={"title": "Tagged", "tags": ["design", "frontend"]}
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["tags"] == ["design", "frontend"]


@pytest.mark.asyncio
async def test_update_tags(authenticated_client: AsyncClient) -> None:
    """Update a page's tags."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Tag Update", "tags": ["old"]}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/wiki/{page_id}", json={"tags": ["new", "updated"]}
    )
    assert response.status_code == 200
    assert response.json()["data"]["tags"] == ["new", "updated"]


@pytest.mark.asyncio
async def test_clear_tags(authenticated_client: AsyncClient) -> None:
    """Setting tags to empty list clears them."""
    create = await authenticated_client.post(
        "/api/wiki", json={"title": "Clear Tags", "tags": ["a", "b"]}
    )
    page_id = create.json()["data"]["id"]

    response = await authenticated_client.put(f"/api/wiki/{page_id}", json={"tags": []})
    assert response.status_code == 200
    assert response.json()["data"]["tags"] == []


@pytest.mark.asyncio
async def test_filter_by_tag(authenticated_client: AsyncClient) -> None:
    """List endpoint can filter by tag."""
    await authenticated_client.post(
        "/api/wiki", json={"title": "Has Tag", "tags": ["python"]}
    )
    await authenticated_client.post("/api/wiki", json={"title": "No Tag", "tags": []})

    response = await authenticated_client.get("/api/wiki", params={"tag": "python"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "Has Tag"


@pytest.mark.asyncio
async def test_tags_in_list_response(authenticated_client: AsyncClient) -> None:
    """Tags are included in list/summary responses."""
    await authenticated_client.post(
        "/api/wiki", json={"title": "List Tags", "tags": ["api", "docs"]}
    )

    response = await authenticated_client.get("/api/wiki")
    assert response.status_code == 200
    page = response.json()["data"][0]
    assert page["tags"] == ["api", "docs"]


@pytest.mark.asyncio
async def test_tags_in_tree_response(authenticated_client: AsyncClient) -> None:
    """Tags are included in tree endpoint responses."""
    await authenticated_client.post(
        "/api/wiki", json={"title": "Tree Tags", "tags": ["arch"]}
    )

    response = await authenticated_client.get("/api/wiki/tree")
    assert response.status_code == 200
    node = response.json()["data"][0]
    assert node["tags"] == ["arch"]
