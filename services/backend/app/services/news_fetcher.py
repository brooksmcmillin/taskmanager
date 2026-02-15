"""RSS news fetching service."""

import ipaddress
import logging
import socket
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.article import Article
from app.models.feed_source import FeedSource

logger = logging.getLogger(__name__)

# Networks that should never be fetched by the RSS fetcher
BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def validate_feed_url(url: str) -> None:
    """Validate that a feed URL does not point to internal/private networks.

    Raises:
        ValueError: If the URL is invalid or points to a blocked network.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        ip = socket.gethostbyname(hostname)
        ip_addr = ipaddress.ip_address(ip)
        for network in BLOCKED_NETWORKS:
            if ip_addr in network:
                raise ValueError(f"URL resolves to blocked network: {ip}")
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from e


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


def parse_feed_datetime(time_tuple) -> datetime:
    """Convert feedparser time tuple to UTC datetime.

    Args:
        time_tuple: Feedparser time.struct_time (9-element tuple)

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime(
        int(time_tuple[0]),  # year
        int(time_tuple[1]),  # month
        int(time_tuple[2]),  # day
        int(time_tuple[3]),  # hour
        int(time_tuple[4]),  # minute
        int(time_tuple[5]),  # second
        tzinfo=UTC,
    )


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


def _parse_feed_entry(
    entry: Any,
) -> tuple[str, str, str, str, str | None, datetime | None]:
    """Parse a feedparser entry into structured article data.

    Returns:
        Tuple of (title, url, summary, content, author, published_at).
    """
    title: str = entry.get("title", "")  # type: ignore
    url: str = entry.get("link", "")  # type: ignore
    summary: str = entry.get("summary", "") or entry.get("description", "")  # type: ignore

    content: str = ""
    content_list = entry.get("content")  # type: ignore
    if content_list and isinstance(content_list, list) and len(content_list) > 0:
        content = content_list[0].get("value", "")  # type: ignore

    author: str | None = entry.get("author", None)  # type: ignore

    published_at = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        published_at = parse_feed_datetime(entry.published_parsed)  # type: ignore
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        published_at = parse_feed_datetime(entry.updated_parsed)  # type: ignore

    return title, url, summary, content, author, published_at


async def _fetch_feed_entries(
    feed_source: FeedSource,
    db: AsyncSession,
    since: datetime | None = None,
) -> int:
    """Fetch and store articles from an RSS feed.

    Args:
        feed_source: The feed source to fetch.
        db: Database session.
        since: If provided, skip entries published before this datetime.

    Returns:
        Number of new articles added.
    """
    label = "Force-fetching" if since else "Fetching"
    since_str = f" since {since.isoformat()}" if since else ""
    logger.info(f"{label} feed: {feed_source.name} ({feed_source.url}){since_str}")

    validate_feed_url(feed_source.url)

    feed = feedparser.parse(feed_source.url)

    if feed.bozo:
        logger.warning(
            f"Feed parsing error for {feed_source.name}: {feed.bozo_exception}"
        )

    new_articles = 0

    for entry in feed.entries:
        title, url, summary, content, author, published_at = _parse_feed_entry(entry)

        # Skip entries published before the cutoff
        if since and published_at and published_at < since:
            continue

        # Check if article already exists
        stmt = select(Article).where(Article.url == url)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            continue

        # Filter by keywords
        matches, keywords = article_matches_keywords(title, summary, content)
        if not matches:
            logger.debug(f"Article filtered out (no keyword match): {title}")
            continue

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

    feed_source.last_fetched_at = datetime.now(UTC)
    await db.commit()

    logger.info(f"Fetched {new_articles} new articles from {feed_source.name}")
    return new_articles


async def fetch_feed(feed_source: FeedSource, db: AsyncSession) -> int:
    """Fetch articles from a single RSS feed."""
    try:
        return await _fetch_feed_entries(feed_source, db)
    except ValueError as e:
        logger.error(f"Invalid feed URL for {feed_source.name}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error fetching feed {feed_source.name}: {e}")
        await db.rollback()
        return 0


async def fetch_feed_since(
    feed_source: FeedSource, db: AsyncSession, since: datetime
) -> int:
    """Fetch articles from a feed, skipping entries published before `since`."""
    try:
        return await _fetch_feed_entries(feed_source, db, since=since)
    except ValueError as e:
        logger.error(f"Invalid feed URL for {feed_source.name}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error force-fetching feed {feed_source.name}: {e}")
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
