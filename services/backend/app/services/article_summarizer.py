"""AI-powered article summarization service using Anthropic API."""

import logging

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import async_session_maker
from app.models.article import Article

logger = logging.getLogger(__name__)

MAX_SOURCE_CHARS = 4000

SYSTEM_PROMPT = (
    "You are a technical article summarizer. Given an article's title, summary, "
    "and/or content, produce a concise 2-3 sentence summary that captures the key "
    "points. Focus on what is new, important, or actionable. Be direct and specific. "
    "Do not start with 'This article' or 'The article'. Just state the key points."
)


def _build_source_text(
    title: str, summary: str | None, content: str | None
) -> str:
    """Combine article fields into source text for summarization."""
    parts = [f"Title: {title}"]
    if summary:
        parts.append(f"Summary: {summary}")
    if content:
        parts.append(f"Content: {content}")
    text = "\n\n".join(parts)
    if len(text) > MAX_SOURCE_CHARS:
        text = text[:MAX_SOURCE_CHARS]
    return text


async def _generate_summary(
    client: anthropic.AsyncAnthropic, article: Article
) -> str | None:
    """Generate an AI summary for a single article."""
    source_text = _build_source_text(article.title, article.summary, article.content)

    response = await client.messages.create(
        model=settings.ai_summary_model,
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": source_text}],
    )

    if response.content and response.content[0].type == "text":
        return response.content[0].text
    return None


async def generate_single_summary(db: AsyncSession, article: Article) -> str | None:
    """Generate an AI summary for a single article.

    Returns the summary text, or None if the API key is not set.
    Raises on API errors (caller should handle).
    """
    if not settings.anthropic_api_key:
        return None

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    summary = await _generate_summary(client, article)
    if summary:
        article.ai_summary = summary
        await db.commit()
    return summary


async def generate_article_summaries_with_session(db: AsyncSession) -> int:
    """Generate AI summaries for articles that don't have one yet.

    Returns the number of articles summarized.
    """
    if not settings.anthropic_api_key:
        logger.debug("ANTHROPIC_API_KEY not set, skipping article summarization")
        return 0

    stmt = (
        select(Article)
        .where(Article.ai_summary.is_(None))
        .order_by(Article.id.desc())
        .limit(settings.ai_summary_batch_size)
    )
    result = await db.execute(stmt)
    articles = result.scalars().all()

    if not articles:
        logger.debug("No articles need summarization")
        return 0

    logger.info("Generating AI summaries for %d articles", len(articles))
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    count = 0

    for article in articles:
        try:
            summary = await _generate_summary(client, article)
            if summary:
                article.ai_summary = summary
                count += 1
        except Exception:
            logger.exception("Failed to generate summary for article %d", article.id)

    if count > 0:
        await db.commit()
        logger.info("Generated %d AI summaries", count)

    return count


async def generate_article_summaries() -> None:
    """Standalone entry point for the scheduler.

    Creates its own database session, same pattern as fetch_all_feeds().
    """
    async with async_session_maker() as db:
        await generate_article_summaries_with_session(db)
