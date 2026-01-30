"""Seed initial AI/LLM security news feed sources."""

import asyncio

from sqlalchemy import select

from app.db.database import async_session_maker
from app.models.feed_source import FeedSource, FeedType

INITIAL_FEEDS = [
    {
        "name": "ArXiv CS.CR (Cryptography and Security)",
        "url": "http://export.arxiv.org/rss/cs.CR",
        "description": "Latest research papers on cryptography and security from ArXiv",
        "type": FeedType.paper,
    },
    {
        "name": "ArXiv CS.AI (Artificial Intelligence)",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "description": "Latest AI research papers from ArXiv",
        "type": FeedType.paper,
    },
    {
        "name": "ArXiv CS.LG (Machine Learning)",
        "url": "http://export.arxiv.org/rss/cs.LG",
        "description": "Latest machine learning research papers from ArXiv",
        "type": FeedType.paper,
    },
    {
        "name": "OWASP Blog",
        "url": "https://owasp.org/www-community/rss.xml",
        "description": "OWASP security community updates",
        "type": FeedType.article,
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.research.google/atom.xml",
        "description": "Research and insights from Google AI",
        "type": FeedType.article,
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "description": "Latest updates and research from OpenAI",
        "type": FeedType.article,
    },
    {
        "name": "Anthropic Blog",
        "url": "https://www.anthropic.com/news/rss.xml",
        "description": "Research and safety updates from Anthropic",
        "type": FeedType.article,
    },
    {
        "name": "Trail of Bits Blog",
        "url": "https://blog.trailofbits.com/feed/",
        "description": "Security research and engineering insights",
        "type": FeedType.article,
    },
    {
        "name": "NIST Cybersecurity Insights",
        "url": "https://www.nist.gov/blogs/cybersecurity-insights/rss.xml",
        "description": "NIST cybersecurity research and standards",
        "type": FeedType.article,
    },
    {
        "name": "The Gradient",
        "url": "https://thegradient.pub/rss/",
        "description": "ML research news and perspectives",
        "type": FeedType.article,
    },
    {
        "name": "Schneier on Security",
        "url": "https://www.schneier.com/feed/",
        "description": "Security expert Bruce Schneier's blog",
        "type": FeedType.article,
    },
    {
        "name": "DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "description": "AI research from Google DeepMind",
        "type": FeedType.article,
    },
]


async def seed_feeds() -> None:
    """Add initial feed sources to the database."""
    async with async_session_maker() as db:
        for feed_data in INITIAL_FEEDS:
            # Check if feed already exists
            stmt = select(FeedSource).where(FeedSource.url == feed_data["url"])
            result = await db.execute(stmt)
            existing_feed = result.scalar_one_or_none()

            if existing_feed:
                # Update type if it doesn't match
                expected_type = feed_data.get("type", FeedType.article)
                if existing_feed.type != expected_type:
                    existing_feed.type = expected_type
                    name = feed_data["name"]
                    print(f"~ Updated type: {name} -> {expected_type.value}")
                else:
                    print(f"✓ Feed already exists: {feed_data['name']}")
                continue

            # Create new feed source
            feed = FeedSource(
                name=feed_data["name"],
                url=feed_data["url"],
                description=feed_data.get("description"),
                type=feed_data.get("type", FeedType.article),
                is_active=True,
                fetch_interval_hours=6,
                quality_score=1.0,
            )
            db.add(feed)
            print(f"+ Added feed: {feed_data['name']}")

        await db.commit()
        print(f"\n✓ Seeded {len(INITIAL_FEEDS)} feed sources")


if __name__ == "__main__":
    print("Seeding AI/LLM security news feed sources...\n")
    asyncio.run(seed_feeds())
    print("\nDone!")
