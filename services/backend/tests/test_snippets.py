"""Tests for the Snippets API."""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_snippets_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/snippets")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_snippet_unauthenticated(client: AsyncClient) -> None:
    response = await client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_snippet(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car Maintenance",
            "title": "Changed air filter",
            "content": "Used K&N filter model 33-2304",
            "snippet_date": "2026-02-28",
            "tags": ["car", "filter"],
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["category"] == "Car Maintenance"
    assert data["title"] == "Changed air filter"
    assert data["content"] == "Used K&N filter model 33-2304"
    assert data["snippet_date"] == "2026-02-28"
    assert data["tags"] == ["car", "filter"]
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_snippet_minimal(authenticated_client: AsyncClient) -> None:
    """Create a snippet with only required fields."""
    response = await authenticated_client.post(
        "/api/snippets",
        json={"category": "Notes", "title": "Quick note"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["category"] == "Notes"
    assert data["title"] == "Quick note"
    assert data["content"] == ""
    assert data["tags"] == []
    assert data["snippet_date"] is not None


@pytest.mark.asyncio
async def test_create_snippet_validation(authenticated_client: AsyncClient) -> None:
    """Missing required fields should return 422."""
    response = await authenticated_client.post(
        "/api/snippets",
        json={"title": "No category"},
    )
    assert response.status_code == 422

    response = await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_snippet(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "Changed HVAC filter"},
    )
    snippet_id = create.json()["data"]["id"]

    response = await authenticated_client.get(f"/api/snippets/{snippet_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == snippet_id
    assert data["title"] == "Changed HVAC filter"


@pytest.mark.asyncio
async def test_get_snippet_not_found(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/snippets/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_snippet(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car",
            "title": "Oil change",
            "snippet_date": "2026-02-01",
        },
    )
    snippet_id = create.json()["data"]["id"]

    response = await authenticated_client.put(
        f"/api/snippets/{snippet_id}",
        json={
            "title": "Oil change - synthetic",
            "content": "5W-30 Mobil 1",
            "tags": ["car", "oil"],
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Oil change - synthetic"
    assert data["content"] == "5W-30 Mobil 1"
    assert data["tags"] == ["car", "oil"]
    # Unchanged fields preserved
    assert data["category"] == "Car"
    assert data["snippet_date"] == "2026-02-01"


@pytest.mark.asyncio
async def test_update_snippet_not_found(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.put(
        "/api/snippets/99999",
        json={"title": "Nope"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_snippet(authenticated_client: AsyncClient) -> None:
    create = await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "Replaced smoke detector battery"},
    )
    snippet_id = create.json()["data"]["id"]

    response = await authenticated_client.delete(f"/api/snippets/{snippet_id}")
    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Should no longer be accessible
    get = await authenticated_client.get(f"/api/snippets/{snippet_id}")
    assert get.status_code == 404


@pytest.mark.asyncio
async def test_delete_snippet_not_found(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.delete("/api/snippets/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# List / filtering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_snippets(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change"},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "HVAC filter"},
    )

    response = await authenticated_client.get("/api/snippets")
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 2
    assert len(data["data"]) == 2


@pytest.mark.asyncio
async def test_list_snippets_filter_category(
    authenticated_client: AsyncClient,
) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change"},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "HVAC filter"},
    )

    response = await authenticated_client.get(
        "/api/snippets", params={"category": "Car"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["category"] == "Car"


@pytest.mark.asyncio
async def test_list_snippets_filter_tag(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change", "tags": ["maintenance"]},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Washed car", "tags": ["cleaning"]},
    )

    response = await authenticated_client.get(
        "/api/snippets", params={"tag": "maintenance"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "Oil change"


@pytest.mark.asyncio
async def test_list_snippets_search(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change"},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "HVAC filter replacement"},
    )

    response = await authenticated_client.get("/api/snippets", params={"q": "HVAC"})
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "HVAC filter replacement"


@pytest.mark.asyncio
async def test_list_snippets_date_range(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car",
            "title": "January oil change",
            "snippet_date": "2026-01-15",
        },
    )
    await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car",
            "title": "February oil change",
            "snippet_date": "2026-02-15",
        },
    )

    response = await authenticated_client.get(
        "/api/snippets",
        params={"date_from": "2026-02-01", "date_to": "2026-02-28"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 1
    assert data["data"][0]["title"] == "February oil change"


@pytest.mark.asyncio
async def test_list_snippets_ordered_by_date_desc(
    authenticated_client: AsyncClient,
) -> None:
    """Snippets should be ordered newest date first."""
    await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car",
            "title": "Old entry",
            "snippet_date": "2026-01-01",
        },
    )
    await authenticated_client.post(
        "/api/snippets",
        json={
            "category": "Car",
            "title": "New entry",
            "snippet_date": "2026-02-28",
        },
    )

    response = await authenticated_client.get("/api/snippets")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data[0]["title"] == "New entry"
    assert data[1]["title"] == "Old entry"


# ---------------------------------------------------------------------------
# Categories endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_categories(authenticated_client: AsyncClient) -> None:
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Oil change"},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "Car", "title": "Tire rotation"},
    )
    await authenticated_client.post(
        "/api/snippets",
        json={"category": "House", "title": "HVAC filter"},
    )

    response = await authenticated_client.get("/api/snippets/categories")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    # Ordered alphabetically
    assert data[0]["category"] == "Car"
    assert data[0]["count"] == 2
    assert data[1]["category"] == "House"
    assert data[1]["count"] == 1


@pytest.mark.asyncio
async def test_list_categories_empty(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/snippets/categories")
    assert response.status_code == 200
    assert response.json()["data"] == []


# ---------------------------------------------------------------------------
# Cross-user isolation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_read_other_users_snippet(
    client: AsyncClient,
    db_session,
) -> None:
    """Users cannot see each other's snippets."""
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="snippet_a1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="snippet_a2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    # Login as user1 and create a snippet
    await client.post(
        "/api/auth/login",
        json={"email": "snippet_a1@example.com", "password": "TestPass123!"},
    )
    create = await client.post(
        "/api/snippets",
        json={"category": "Secret", "title": "My private note"},
    )
    snippet_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    # Login as user2 and try to access user1's snippet
    await client.post(
        "/api/auth/login",
        json={"email": "snippet_a2@example.com", "password": "TestPass123!"},
    )
    response = await client.get(f"/api/snippets/{snippet_id}")
    assert response.status_code == 404

    # Also should not appear in list
    list_resp = await client.get("/api/snippets")
    assert list_resp.json()["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_cannot_update_other_users_snippet(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="snippet_b1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="snippet_b2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    await client.post(
        "/api/auth/login",
        json={"email": "snippet_b1@example.com", "password": "TestPass123!"},
    )
    create = await client.post(
        "/api/snippets",
        json={"category": "Private", "title": "User1 snippet"},
    )
    snippet_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={"email": "snippet_b2@example.com", "password": "TestPass123!"},
    )
    response = await client.put(
        f"/api/snippets/{snippet_id}",
        json={"title": "Hacked!"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cannot_delete_other_users_snippet(
    client: AsyncClient,
    db_session,
) -> None:
    from app.core.security import hash_password
    from app.models.user import User

    user1 = User(
        email="snippet_c1@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    user2 = User(
        email="snippet_c2@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
    )
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    await client.post(
        "/api/auth/login",
        json={"email": "snippet_c1@example.com", "password": "TestPass123!"},
    )
    create = await client.post(
        "/api/snippets",
        json={"category": "Private", "title": "Do not delete"},
    )
    snippet_id = create.json()["data"]["id"]
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={"email": "snippet_c2@example.com", "password": "TestPass123!"},
    )
    response = await client.delete(f"/api/snippets/{snippet_id}")
    assert response.status_code == 404
