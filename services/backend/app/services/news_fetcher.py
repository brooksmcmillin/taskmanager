"""RSS news fetching service."""

import logging
from datetime import UTC, datetime

import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.article import Article
from app.models.feed_source import FeedSource

logger = logging.getLogger(__name__)

# AI/LLM security keywords to filter articles
SECURITY_KEYWORDS = [
    "llm security",
    "ai security",
    "prompt injection",
    "jailbreak",
    "adversarial",
    "model safety",
    "ai safety",
    "machine learning security",
    "deep learning security",
    "neural network attack",
    "model poisoning",
    "backdoor attack",
    "data poisoning",
    "membership inference",
    "model extraction",
    "privacy attack",
    "federated learning security",
    "transformer security",
    "gpt security",
    "language model",
    "generative ai",
    "foundation model",
    "alignment",
    "rlhf",
    "constitutional ai",
    "red teaming",
]


def article_matches_keywords(
    title: str, summary: str, content: str
) -> tuple[bool, list[str]]:
    """Check if article matches AI/LLM security keywords."""
    text = f"{title} {summary} {content}".lower()
    matched_keywords = []

    for keyword in SECURITY_KEYWORDS:
        if keyword.lower() in text:
            matched_keywords.append(keyword)

    return len(matched_keywords) > 0, matched_keywords


async def fetch_feed(feed_source: FeedSource, db: AsyncSession) -> int:
    """Fetch articles from a single RSS feed."""
    try:
        logger.info(f"Fetching feed: {feed_source.name} ({feed_source.url})")

        # Parse the RSS feed
        feed = feedparser.parse(feed_source.url)

        if feed.bozo:
            logger.warning(
                f"Feed parsing error for {feed_source.name}: {feed.bozo_exception}"
            )

        new_articles = 0

        for entry in feed.entries:
            # Extract article data
            title: str = entry.get("title", "")  # type: ignore
            url: str = entry.get("link", "")  # type: ignore
            summary: str = entry.get("summary", "") or entry.get("description", "")  # type: ignore

            # Extract content from nested structure
            content: str = ""
            content_list = entry.get("content")  # type: ignore
            if (
                content_list
                and isinstance(content_list, list)
                and len(content_list) > 0
            ):
                content = content_list[0].get("value", "")  # type: ignore

            author: str | None = entry.get("author", None)  # type: ignore

            # Parse published date
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                time_tuple = entry.published_parsed  # type: ignore
                published_at = datetime(
                    int(time_tuple[0]),  # year  # type: ignore
                    int(time_tuple[1]),  # month  # type: ignore
                    int(time_tuple[2]),  # day  # type: ignore
                    int(time_tuple[3]),  # hour  # type: ignore
                    int(time_tuple[4]),  # minute  # type: ignore
                    int(time_tuple[5]),  # second  # type: ignore
                    tzinfo=UTC,
                )
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                time_tuple = entry.updated_parsed  # type: ignore
                published_at = datetime(
                    int(time_tuple[0]),  # year  # type: ignore
                    int(time_tuple[1]),  # month  # type: ignore
                    int(time_tuple[2]),  # day  # type: ignore
                    int(time_tuple[3]),  # hour  # type: ignore
                    int(time_tuple[4]),  # minute  # type: ignore
                    int(time_tuple[5]),  # second  # type: ignore
                    tzinfo=UTC,
                )

            # Check if article already exists
            stmt = select(Article).where(Article.url == url)
            result = await db.execute(stmt)
            existing_article = result.scalar_one_or_none()

            if existing_article:
                continue

            # Filter by keywords
            matches, keywords = article_matches_keywords(title, summary, content)
            if not matches:
                logger.debug(f"Article filtered out (no keyword match): {title}")
                continue

            # Create new article
            article = Article(
                feed_source_id=feed_source.id,
                title=title,
                url=url,
                summary=summary,
                content=content,
                author=author,
                published_at=published_at,
                keywords=keywords,
            )
            db.add(article)
            new_articles += 1
            logger.info(f"Added article: {title}")

        # Update last fetched timestamp
        feed_source.last_fetched_at = datetime.now(UTC)
        await db.commit()

        logger.info(f"Fetched {new_articles} new articles from {feed_source.name}")
        return new_articles

    except Exception as e:
        logger.error(f"Error fetching feed {feed_source.name}: {e}")
        await db.rollback()
        return 0


async def fetch_all_feeds() -> dict[str, int]:
    """Fetch articles from all active feeds."""
    logger.info("Starting feed fetch job")

    async with async_session_maker() as db:
        # Get all active feed sources
        stmt = select(FeedSource).where(FeedSource.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        feed_sources = result.scalars().all()

        if not feed_sources:
            logger.warning("No active feed sources found")
            return {}

        results = {}
        for feed_source in feed_sources:
            count = await fetch_feed(feed_source, db)
            results[feed_source.name] = count

    logger.info(f"Feed fetch job completed: {results}")
    return results
