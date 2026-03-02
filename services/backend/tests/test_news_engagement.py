"""Tests for news engagement features: stats, bookmarks, and daily highlight."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_interaction import ArticleInteraction
from app.models.feed_source import FeedSource, FeedType
from app.models.user import User


@pytest_asyncio.fixture
async def featured_source(db_session: AsyncSession) -> FeedSource:
    """Create a featured, active feed source."""
    source = FeedSource(
        name="Featured Source",
        url="https://featured.example.com/feed.xml",
        type=FeedType.article,
        is_active=True,
        is_featured=True,
        quality_score=1.5,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest_asyncio.fixture
async def sample_articles(
    db_session: AsyncSession, featured_source: FeedSource
) -> list[Article]:
    """Create sample articles across several days."""
    now = datetime.now(UTC)
    articles = []
    for i in range(5):
        article = Article(
            feed_source_id=featured_source.id,
            title=f"Article {i}",
            url=f"https://example.com/article/{i}",
            summary=f"Summary for article {i}",
            published_at=now - timedelta(days=i),
            keywords=["ai security"],
        )
        db_session.add(article)
        articles.append(article)
    await db_session.commit()
    for a in articles:
        await db_session.refresh(a)
    return articles


# =============================================================================
# GET /api/news/stats
# =============================================================================


class TestReadingStats:
    @pytest.mark.asyncio
    async def test_stats_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/news/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_stats_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/news/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["streak_days"] == 0
        assert data["articles_read_today"] == 0
        assert data["articles_read_this_week"] == 0
        assert data["total_articles_read"] == 0
        assert data["total_bookmarked"] == 0

    @pytest.mark.asyncio
    async def test_stats_with_reads(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        sample_articles: list[Article],
        db_session: AsyncSession,
    ):
        # Mark two articles as read today
        now = datetime.now(UTC)
        for article in sample_articles[:2]:
            interaction = ArticleInteraction(
                user_id=test_user.id,
                article_id=article.id,
                is_read=True,
                read_at=now,
            )
            db_session.add(interaction)
        await db_session.commit()

        response = await authenticated_client.get("/api/news/stats")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["articles_read_today"] == 2
        assert data["articles_read_this_week"] >= 2
        assert data["total_articles_read"] == 2
        assert data["streak_days"] >= 1

    @pytest.mark.asyncio
    async def test_stats_streak_consecutive_days(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        sample_articles: list[Article],
        db_session: AsyncSession,
    ):
        """Streak counts consecutive days with reads, including today."""
        now = datetime.now(UTC)
        # Read articles on today, yesterday, and 2 days ago
        for i in range(3):
            interaction = ArticleInteraction(
                user_id=test_user.id,
                article_id=sample_articles[i].id,
                is_read=True,
                read_at=now - timedelta(days=i),
            )
            db_session.add(interaction)
        await db_session.commit()

        response = await authenticated_client.get("/api/news/stats")
        assert response.status_code == 200
        assert response.json()["data"]["streak_days"] == 3

    @pytest.mark.asyncio
    async def test_stats_bookmarked_count(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        sample_articles: list[Article],
        db_session: AsyncSession,
    ):
        interaction = ArticleInteraction(
            user_id=test_user.id,
            article_id=sample_articles[0].id,
            is_bookmarked=True,
            bookmarked_at=datetime.now(UTC),
        )
        db_session.add(interaction)
        await db_session.commit()

        response = await authenticated_client.get("/api/news/stats")
        assert response.status_code == 200
        assert response.json()["data"]["total_bookmarked"] == 1


# =============================================================================
# GET /api/news/highlight
# =============================================================================


class TestDailyHighlight:
    @pytest.mark.asyncio
    async def test_highlight_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/news/highlight")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_highlight_empty(self, authenticated_client: AsyncClient):
        response = await authenticated_client.get("/api/news/highlight")
        assert response.status_code == 200
        assert response.json()["data"] is None

    @pytest.mark.asyncio
    async def test_highlight_returns_unread_article(
        self,
        authenticated_client: AsyncClient,
        sample_articles: list[Article],
    ):
        response = await authenticated_client.get("/api/news/highlight")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data is not None
        assert data["is_read"] is False
        assert "title" in data
        assert "url" in data

    @pytest.mark.asyncio
    async def test_highlight_skips_read_articles(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        sample_articles: list[Article],
        db_session: AsyncSession,
    ):
        # Mark all articles as read
        for article in sample_articles:
            interaction = ArticleInteraction(
                user_id=test_user.id,
                article_id=article.id,
                is_read=True,
                read_at=datetime.now(UTC),
            )
            db_session.add(interaction)
        await db_session.commit()

        response = await authenticated_client.get("/api/news/highlight")
        assert response.status_code == 200
        assert response.json()["data"] is None


# =============================================================================
# POST /api/news/{article_id}/bookmark
# =============================================================================


class TestBookmarkArticle:
    @pytest.mark.asyncio
    async def test_bookmark_unauthenticated(
        self, client: AsyncClient, sample_articles: list[Article]
    ):
        response = await client.post(
            f"/api/news/{sample_articles[0].id}/bookmark",
            json={"is_bookmarked": True},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_bookmark_not_found(self, authenticated_client: AsyncClient):
        response = await authenticated_client.post(
            "/api/news/99999/bookmark",
            json={"is_bookmarked": True},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_bookmark_article(
        self,
        authenticated_client: AsyncClient,
        sample_articles: list[Article],
    ):
        article_id = sample_articles[0].id
        response = await authenticated_client.post(
            f"/api/news/{article_id}/bookmark",
            json={"is_bookmarked": True},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_bookmarked"] is True
        assert data["article_id"] == article_id

    @pytest.mark.asyncio
    async def test_unbookmark_article(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        sample_articles: list[Article],
        db_session: AsyncSession,
    ):
        article_id = sample_articles[0].id

        # Create existing bookmark
        interaction = ArticleInteraction(
            user_id=test_user.id,
            article_id=article_id,
            is_bookmarked=True,
            bookmarked_at=datetime.now(UTC),
        )
        db_session.add(interaction)
        await db_session.commit()

        response = await authenticated_client.post(
            f"/api/news/{article_id}/bookmark",
            json={"is_bookmarked": False},
        )
        assert response.status_code == 200
        assert response.json()["data"]["is_bookmarked"] is False

    @pytest.mark.asyncio
    async def test_bookmark_shows_in_list(
        self,
        authenticated_client: AsyncClient,
        sample_articles: list[Article],
    ):
        article_id = sample_articles[0].id

        # Bookmark the article
        await authenticated_client.post(
            f"/api/news/{article_id}/bookmark",
            json={"is_bookmarked": True},
        )

        # Verify it shows in bookmarked filter
        response = await authenticated_client.get(
            "/api/news", params={"bookmarked_only": "true"}
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == article_id
        assert data[0]["is_bookmarked"] is True

    @pytest.mark.asyncio
    async def test_bookmarked_filter_excludes_unbookmarked(
        self,
        authenticated_client: AsyncClient,
        sample_articles: list[Article],
    ):
        """Bookmarked filter returns empty when nothing is bookmarked."""
        response = await authenticated_client.get(
            "/api/news", params={"bookmarked_only": "true"}
        )
        assert response.status_code == 200
        assert len(response.json()["data"]) == 0
