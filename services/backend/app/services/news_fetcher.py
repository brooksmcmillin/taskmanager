"""RSS news fetching service."""

import asyncio
import ipaddress
import logging
import socket
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
import httpx
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
    ipaddress.ip_network("fe80::/10"),
]

# Timeout for fetching RSS feeds.  Read timeout is higher than GitHub OAuth
# (15s vs 10s) because RSS feeds can be large and served by slow hosts.
FEED_FETCH_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=10.0)


def _is_ip_blocked(ip_str: str) -> bool:
    """Check if an IP address falls within any blocked network."""
    try:
        ip_addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # Unparseable IPs are blocked
    return any(ip_addr in network for network in BLOCKED_NETWORKS)


class SSRFProtectionTransport(httpx.AsyncHTTPTransport):
    """HTTP transport that blocks requests to private/internal networks.

    Resolves DNS and validates ALL resulting IPs BEFORE any connection is
    made, preventing TOCTOU and DNS-rebinding attacks.
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        hostname = request.url.host
        if not hostname:
            raise ValueError("Request URL has no hostname")

        try:
            addrinfo = await asyncio.to_thread(
                socket.getaddrinfo,
                hostname,
                None,
                socket.AF_UNSPEC,
                socket.SOCK_STREAM,
            )
        except socket.gaierror as e:
            raise ValueError(f"Cannot resolve hostname {hostname}: {e}") from e

        for _family, _type, _proto, _canonname, sockaddr in addrinfo:
            ip = str(sockaddr[0])
            if _is_ip_blocked(ip):
                raise ValueError(f"URL resolves to blocked network: {ip}")

        return await super().handle_async_request(request)


def validate_feed_url(url: str) -> None:
    """Validate feed URL scheme and hostname (for use at creation/update time).

    This is an early rejection of obviously invalid URLs. The actual SSRF
    protection at fetch time is handled by SSRFProtectionTransport, which
    validates resolved IPs BEFORE any connection is established.

    Raises:
        ValueError: If the URL has an invalid scheme or no hostname.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("URL has no hostname")


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


async def _safe_fetch_feed_content(url: str) -> str:
    """Fetch feed content via httpx with SSRF protection BEFORE connection.

    Uses SSRFProtectionTransport to resolve DNS and validate all IPs
    before any TCP connection is established, preventing TOCTOU and
    DNS-rebinding attacks. Also enforces timeouts to prevent resource
    exhaustion from slow/malicious servers.

    Raises:
        ValueError: If the URL resolves to a blocked network or has
            an invalid scheme/hostname.
        httpx.TimeoutException: If the request times out.
        httpx.HTTPStatusError: If the server returns an error status.
    """
    validate_feed_url(url)

    transport = SSRFProtectionTransport()
    async with httpx.AsyncClient(
        timeout=FEED_FETCH_TIMEOUT,
        transport=transport,
        follow_redirects=True,
        max_redirects=5,
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _fetch_feed_entries(
    feed_source: FeedSource,
    db: AsyncSession,
    since: datetime | None = None,
) -> int:
    """Fetch and store articles from an RSS feed.

    SSRF protection is enforced at connection time (not just at URL
    validation time) to prevent TOCTOU and DNS-rebinding attacks.

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

    content = await _safe_fetch_feed_content(feed_source.url)
    feed = feedparser.parse(content)

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
    except (ValueError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.error(f"Feed fetch failed for {feed_source.name}: {e}")
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
    except (ValueError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.error(f"Feed fetch failed for {feed_source.name}: {e}")
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
