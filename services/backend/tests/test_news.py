"""Tests for news feed API endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.feed_source import FeedSource, FeedType
from app.models.user import User

ADMIN_PASSWORD = "AdminPass123!"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Create an authenticated admin client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def sample_source(db_session: AsyncSession) -> FeedSource:
    """Create a sample feed source."""
    source = FeedSource(
        name="Test Source",
        url="https://example.com/feed.xml",
        description="A test feed source",
        type=FeedType.article,
        is_active=True,
        is_featured=False,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest_asyncio.fixture
async def featured_source(db_session: AsyncSession) -> FeedSource:
    """Create a featured feed source."""
    source = FeedSource(
        name="Featured Source",
        url="https://featured.com/feed.xml",
        description="A featured feed source",
        type=FeedType.paper,
        is_active=True,
        is_featured=True,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


# =============================================================================
# GET /api/news/sources - List feed sources
# =============================================================================


class TestListFeedSources:
    @pytest.mark.asyncio
    async def test_list_sources_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/news/sources")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sources_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/news/sources")
        assert response.status_code == 200
        data = response.json()
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_sources_returns_all(
        self,
        authenticated_client: AsyncClient,
        sample_source: FeedSource,
        featured_source: FeedSource,
    ):
        response = await authenticated_client.get("/api/news/sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    @pytest.mark.asyncio
    async def test_list_sources_filter_featured_true(
        self,
        authenticated_client: AsyncClient,
        sample_source: FeedSource,
        featured_source: FeedSource,
    ):
        response = await authenticated_client.get(
            "/api/news/sources", params={"featured": "true"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Featured Source"
        assert data["data"][0]["is_featured"] is True

    @pytest.mark.asyncio
    async def test_list_sources_filter_featured_false(
        self,
        authenticated_client: AsyncClient,
        sample_source: FeedSource,
        featured_source: FeedSource,
    ):
        response = await authenticated_client.get(
            "/api/news/sources", params={"featured": "false"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Test Source"
        assert data["data"][0]["is_featured"] is False


# =============================================================================
# POST /api/news/sources - Create feed source
# =============================================================================


class TestCreateFeedSource:
    @pytest.mark.asyncio
    async def test_create_source_unauthenticated(self, client: AsyncClient):
        response = await client.post(
            "/api/news/sources",
            json={"name": "New Source", "url": "https://new.com/feed.xml"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_source_non_admin(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post(
            "/api/news/sources",
            json={"name": "New Source", "url": "https://new.com/feed.xml"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_source_success(self, admin_client: AsyncClient):
        response = await admin_client.post(
            "/api/news/sources",
            json={
                "name": "New Source",
                "url": "https://new.com/feed.xml",
                "description": "A new feed source",
                "type": "article",
                "is_featured": True,
                "fetch_interval_hours": 12,
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "New Source"
        assert data["url"] == "https://new.com/feed.xml"
        assert data["description"] == "A new feed source"
        assert data["type"] == "article"
        assert data["is_featured"] is True
        assert data["fetch_interval_hours"] == 12

    @pytest.mark.asyncio
    async def test_create_source_minimal(self, admin_client: AsyncClient):
        response = await admin_client.post(
            "/api/news/sources",
            json={"name": "Minimal Source", "url": "https://minimal.com/feed.xml"},
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["name"] == "Minimal Source"
        assert data["is_active"] is True
        assert data["is_featured"] is False
        assert data["fetch_interval_hours"] == 6

    @pytest.mark.asyncio
    async def test_create_source_duplicate_name(
        self, admin_client: AsyncClient, sample_source: FeedSource
    ):
        response = await admin_client.post(
            "/api/news/sources",
            json={
                "name": sample_source.name,
                "url": "https://different.com/feed.xml",
            },
        )
        assert response.status_code == 400
        assert "name" in response.json()["detail"]["message"].lower()

    @pytest.mark.asyncio
    async def test_create_source_duplicate_url(
        self, admin_client: AsyncClient, sample_source: FeedSource
    ):
        response = await admin_client.post(
            "/api/news/sources",
            json={
                "name": "Different Name",
                "url": sample_source.url,
            },
        )
        assert response.status_code == 400
        assert "url" in response.json()["detail"]["message"].lower()


# =============================================================================
# PUT /api/news/sources/{source_id} - Update feed source
# =============================================================================


class TestUpdateFeedSource:
    @pytest.mark.asyncio
    async def test_update_source_unauthenticated(
        self, client: AsyncClient, sample_source: FeedSource
    ):
        response = await client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_source_non_admin(
        self, authenticated_client: AsyncClient, sample_source: FeedSource
    ):
        response = await authenticated_client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_source_success(
        self, admin_client: AsyncClient, sample_source: FeedSource
    ):
        response = await admin_client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"name": "Updated Name", "description": "Updated description"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        # Unchanged fields should remain
        assert data["url"] == sample_source.url

    @pytest.mark.asyncio
    async def test_update_source_not_found(self, admin_client: AsyncClient):
        response = await admin_client.put(
            "/api/news/sources/99999",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_source_duplicate_name(
        self,
        admin_client: AsyncClient,
        sample_source: FeedSource,
        featured_source: FeedSource,
    ):
        response = await admin_client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"name": featured_source.name},
        )
        assert response.status_code == 400
        assert "name" in response.json()["detail"]["message"].lower()

    @pytest.mark.asyncio
    async def test_update_source_duplicate_url(
        self,
        admin_client: AsyncClient,
        sample_source: FeedSource,
        featured_source: FeedSource,
    ):
        response = await admin_client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"url": featured_source.url},
        )
        assert response.status_code == 400
        assert "url" in response.json()["detail"]["message"].lower()

    @pytest.mark.asyncio
    async def test_update_source_same_name_no_conflict(
        self, admin_client: AsyncClient, sample_source: FeedSource
    ):
        """Updating a source with its own current name should not conflict."""
        response = await admin_client.put(
            f"/api/news/sources/{sample_source.id}",
            json={"name": sample_source.name, "description": "Changed desc"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["description"] == "Changed desc"


# =============================================================================
# DELETE /api/news/sources/{source_id} - Delete feed source
# =============================================================================


class TestDeleteFeedSource:
    @pytest.mark.asyncio
    async def test_delete_source_unauthenticated(
        self, client: AsyncClient, sample_source: FeedSource
    ):
        response = await client.delete(f"/api/news/sources/{sample_source.id}")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_source_non_admin(
        self, authenticated_client: AsyncClient, sample_source: FeedSource
    ):
        response = await authenticated_client.delete(
            f"/api/news/sources/{sample_source.id}"
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_source_success(
        self, admin_client: AsyncClient, sample_source: FeedSource
    ):
        response = await admin_client.delete(f"/api/news/sources/{sample_source.id}")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["deleted"] is True
        assert body["data"]["id"] == sample_source.id
        assert body["meta"]["articles_deleted"] == 0

        # Verify source is gone
        response = await admin_client.get("/api/news/sources")
        assert response.status_code == 200
        assert len(response.json()["data"]) == 0

    @pytest.mark.asyncio
    async def test_delete_source_not_found(self, admin_client: AsyncClient):
        response = await admin_client.delete("/api/news/sources/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_source_cascades_articles(
        self,
        admin_client: AsyncClient,
        sample_source: FeedSource,
        db_session: AsyncSession,
    ):
        """Deleting a source should also delete its articles."""
        from app.models.article import Article

        article = Article(
            feed_source_id=sample_source.id,
            title="Test Article",
            url="https://example.com/article/1",
            summary="Test summary",
            keywords=[],
        )
        db_session.add(article)
        await db_session.commit()

        response = await admin_client.delete(f"/api/news/sources/{sample_source.id}")
        assert response.status_code == 200
        assert response.json()["meta"]["articles_deleted"] == 1

        # Verify article is also deleted
        from sqlalchemy import select

        result = await db_session.execute(
            select(Article).where(Article.feed_source_id == sample_source.id)
        )
        assert result.scalar_one_or_none() is None
