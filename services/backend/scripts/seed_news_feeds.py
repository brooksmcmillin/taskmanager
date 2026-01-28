"""Seed initial AI/LLM security news feed sources."""

import asyncio

from sqlalchemy import select

from app.db.database import async_session_maker
from app.models.feed_source import FeedSource

INITIAL_FEEDS = [
    {
        "name": "ArXiv CS.CR (Cryptography and Security)",
        "url": "http://export.arxiv.org/rss/cs.CR",
        "description": "Latest research papers on cryptography and security from ArXiv",
    },
    {
        "name": "ArXiv CS.AI (Artificial Intelligence)",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "description": "Latest AI research papers from ArXiv",
    },
    {
        "name": "ArXiv CS.LG (Machine Learning)",
        "url": "http://export.arxiv.org/rss/cs.LG",
        "description": "Latest machine learning research papers from ArXiv",
    },
    {
        "name": "OWASP Blog",
        "url": "https://owasp.org/www-community/rss.xml",
        "description": "OWASP security community updates",
    },
    {
        "name": "Google AI Blog",
        "url": "https://blog.research.google/atom.xml",
        "description": "Research and insights from Google AI",
    },
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/blog/rss.xml",
        "description": "Latest updates and research from OpenAI",
    },
    {
        "name": "Anthropic Blog",
        "url": "https://www.anthropic.com/news/rss.xml",
        "description": "Research and safety updates from Anthropic",
    },
    {
        "name": "Trail of Bits Blog",
        "url": "https://blog.trailofbits.com/feed/",
        "description": "Security research and engineering insights",
    },
    {
        "name": "NIST Cybersecurity Insights",
        "url": "https://www.nist.gov/blogs/cybersecurity-insights/rss.xml",
        "description": "NIST cybersecurity research and standards",
    },
    {
        "name": "The Gradient",
        "url": "https://thegradient.pub/rss/",
        "description": "ML research news and perspectives",
    },
    {
        "name": "Schneier on Security",
        "url": "https://www.schneier.com/feed/",
        "description": "Security expert Bruce Schneier's blog",
    },
    {
        "name": "DeepMind Blog",
        "url": "https://deepmind.google/blog/rss.xml",
        "description": "AI research from Google DeepMind",
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
                print(f"✓ Feed already exists: {feed_data['name']}")
                continue

            # Create new feed source
            feed = FeedSource(
                name=feed_data["name"],
                url=feed_data["url"],
                description=feed_data.get("description"),
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
