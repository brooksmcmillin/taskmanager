"""Tests for AI article summarization service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.feed_source import FeedSource, FeedType
from app.services.article_summarizer import (
    _build_source_text,
    generate_article_summaries_with_session,
)


class TestBuildSourceText:
    def test_title_only(self):
        result = _build_source_text("My Title", None, None)
        assert result == "Title: My Title"

    def test_all_fields(self):
        result = _build_source_text("Title", "Summary text", "Content text")
        assert "Title: Title" in result
        assert "Summary: Summary text" in result
        assert "Content: Content text" in result

    def test_truncation(self):
        long_content = "x" * 5000
        result = _build_source_text("Title", None, long_content)
        assert len(result) == 4000

    def test_title_and_summary_only(self):
        result = _build_source_text("Title", "A summary", None)
        assert "Title: Title" in result
        assert "Summary: A summary" in result
        assert "Content:" not in result

    def test_title_and_content_only(self):
        result = _build_source_text("Title", None, "Some content")
        assert "Title: Title" in result
        assert "Summary:" not in result
        assert "Content: Some content" in result


@pytest_asyncio.fixture
async def feed_source(db_session: AsyncSession) -> FeedSource:
    source = FeedSource(
        name="Test Source",
        url="https://example.com/feed.xml",
        type=FeedType.article,
        is_active=True,
        is_featured=False,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


@pytest_asyncio.fixture
async def article_without_summary(
    db_session: AsyncSession, feed_source: FeedSource
) -> Article:
    article = Article(
        feed_source_id=feed_source.id,
        title="Test Article",
        url="https://example.com/article/1",
        summary="Original RSS summary",
        keywords=[],
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def article_with_summary(
    db_session: AsyncSession, feed_source: FeedSource
) -> Article:
    article = Article(
        feed_source_id=feed_source.id,
        title="Already Summarized",
        url="https://example.com/article/2",
        summary="RSS summary",
        ai_summary="Existing AI summary",
        keywords=[],
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


class TestGenerateArticleSummaries:
    @pytest.mark.asyncio
    @patch("app.services.article_summarizer.settings")
    async def test_skips_when_no_api_key(
        self,
        mock_settings: MagicMock,
        db_session: AsyncSession,
        article_without_summary: Article,
    ):
        mock_settings.anthropic_api_key = ""
        count = await generate_article_summaries_with_session(db_session)
        assert count == 0
        # Article should still have no AI summary
        await db_session.refresh(article_without_summary)
        assert article_without_summary.ai_summary is None

    @pytest.mark.asyncio
    @patch("app.services.article_summarizer.anthropic")
    @patch("app.services.article_summarizer.settings")
    async def test_generates_summary(
        self,
        mock_settings: MagicMock,
        mock_anthropic: MagicMock,
        db_session: AsyncSession,
        article_without_summary: Article,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.ai_summary_model = "claude-haiku-4-5-20251001"
        mock_settings.ai_summary_batch_size = 20

        # Mock the API response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Generated AI summary of the article."

        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        count = await generate_article_summaries_with_session(db_session)
        assert count == 1

        await db_session.refresh(article_without_summary)
        assert article_without_summary.ai_summary == "Generated AI summary of the article."

    @pytest.mark.asyncio
    @patch("app.services.article_summarizer.anthropic")
    @patch("app.services.article_summarizer.settings")
    async def test_skips_already_summarized(
        self,
        mock_settings: MagicMock,
        mock_anthropic: MagicMock,
        db_session: AsyncSession,
        article_with_summary: Article,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.ai_summary_model = "claude-haiku-4-5-20251001"
        mock_settings.ai_summary_batch_size = 20

        mock_client = AsyncMock()
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        count = await generate_article_summaries_with_session(db_session)
        assert count == 0
        # API should not have been called
        mock_client.messages.create.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.article_summarizer.anthropic")
    @patch("app.services.article_summarizer.settings")
    async def test_handles_api_failure_gracefully(
        self,
        mock_settings: MagicMock,
        mock_anthropic: MagicMock,
        db_session: AsyncSession,
        article_without_summary: Article,
    ):
        mock_settings.anthropic_api_key = "test-key"
        mock_settings.ai_summary_model = "claude-haiku-4-5-20251001"
        mock_settings.ai_summary_batch_size = 20

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_anthropic.AsyncAnthropic.return_value = mock_client

        # Should not raise
        count = await generate_article_summaries_with_session(db_session)
        assert count == 0

        # Article should still have no AI summary
        await db_session.refresh(article_without_summary)
        assert article_without_summary.ai_summary is None
