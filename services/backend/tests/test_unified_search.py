"""Tests for the Unified Search API."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.feed_source import FeedSource
from app.models.snippet import Snippet
from app.models.todo import Todo
from app.models.wiki_page import WikiPage


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated(client: AsyncClient) -> None:
    response = await client.get("/api/search", params={"q": "test"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_query(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/search")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_query(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get("/api/search", params={"q": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Result structure tests
# ---------------------------------------------------------------------------


async def _seed_data(db: AsyncSession, user_id: int) -> dict:
    """Create one of each searchable type and return their IDs."""
    task = Todo(user_id=user_id, title="Searchable task alpha", status="pending", priority="medium")
    db.add(task)

    wiki = WikiPage(user_id=user_id, title="Searchable wiki alpha", slug="searchable-wiki-alpha", content="Body with alpha keyword")
    db.add(wiki)

    snippet = Snippet(user_id=user_id, category="notes", title="Searchable snippet alpha", content="Alpha content", snippet_date=date(2026, 3, 1))
    db.add(snippet)

    feed = FeedSource(name="Test Feed", url="https://example.com/feed.xml")
    db.add(feed)
    await db.flush()

    article = Article(feed_source_id=feed.id, title="Searchable article alpha", url="https://example.com/alpha", summary="Alpha summary")
    db.add(article)
    await db.flush()

    return {"task_id": task.id, "wiki_id": wiki.id, "snippet_id": snippet.id, "article_id": article.id}


@pytest.mark.asyncio
async def test_returns_grouped_results(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user,
) -> None:
    await _seed_data(db_session, test_user.id)
    await db_session.commit()

    response = await authenticated_client.get("/api/search", params={"q": "alpha"})
    assert response.status_code == 200

    body = response.json()["data"]
    results = body["results"]
    meta = body["meta"]

    # All 4 types should be present
    assert "task" in results
    assert "wiki" in results
    assert "snippet" in results
    assert "article" in results
    assert meta["total"] >= 4

    # Verify structure of a task result
    task_results = results["task"]
    assert len(task_results) >= 1
    item = task_results[0]
    assert item["type"] == "task"
    assert "id" in item
    assert "title" in item
    assert "url" in item

    # Verify wiki result has url with slug
    wiki_results = results["wiki"]
    assert len(wiki_results) >= 1
    assert wiki_results[0]["url"].startswith("/wiki/")


@pytest.mark.asyncio
async def test_types_filter(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user,
) -> None:
    await _seed_data(db_session, test_user.id)
    await db_session.commit()

    response = await authenticated_client.get(
        "/api/search", params={"q": "alpha", "types": "task,wiki"}
    )
    assert response.status_code == 200

    results = response.json()["data"]["results"]
    assert "task" in results
    assert "wiki" in results
    assert "snippet" not in results
    assert "article" not in results


@pytest.mark.asyncio
async def test_limit_caps_per_type(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user,
) -> None:
    # Create multiple tasks
    for i in range(5):
        db_session.add(
            Todo(user_id=test_user.id, title=f"Limit test beta {i}", status="pending", priority="low")
        )
    await db_session.commit()

    response = await authenticated_client.get(
        "/api/search", params={"q": "beta", "types": "task", "limit": 2}
    )
    assert response.status_code == 200
    assert len(response.json()["data"]["results"]["task"]) <= 2


@pytest.mark.asyncio
async def test_no_results(authenticated_client: AsyncClient) -> None:
    response = await authenticated_client.get(
        "/api/search", params={"q": "xyznonexistent999"}
    )
    assert response.status_code == 200
    meta = response.json()["data"]["meta"]
    assert meta["total"] == 0


@pytest.mark.asyncio
async def test_cross_user_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
) -> None:
    """Results from other users should not be returned."""
    from app.core.security import hash_password
    from app.models.user import User

    # Create another user with data
    other_user = User(email="other@example.com", password_hash=hash_password("OtherPass1!"))
    db_session.add(other_user)
    await db_session.flush()

    db_session.add(
        Todo(user_id=other_user.id, title="Gamma secret task", status="pending", priority="high")
    )
    db_session.add(
        WikiPage(user_id=other_user.id, title="Gamma secret wiki", slug="gamma-secret", content="secret")
    )
    await db_session.commit()

    # Login as test_user
    await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "TestPass123!"},
    )

    response = await client.get(
        "/api/search", params={"q": "gamma", "types": "task,wiki"}
    )
    assert response.status_code == 200

    results = response.json()["data"]["results"]
    task_results = results.get("task", [])
    wiki_results = results.get("wiki", [])
    assert len(task_results) == 0
    assert len(wiki_results) == 0
