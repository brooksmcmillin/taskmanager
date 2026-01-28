# Feed Sources Data

This directory contains the initial feed source data for the AI/LLM security news aggregator.

## Files

- **feed_sources.json** - JSON export of all feed sources
- **feed_sources.sql** - SQL import script for feed sources

## Import Options

### Option 1: Using the Python Seed Script (Recommended)

```bash
cd services/backend
uv run python scripts/seed_news_feeds.py
```

This script is idempotent - it will skip feeds that already exist.

### Option 2: Using SQL Import

```bash
# Connect to your database and run the SQL file
psql -d taskmanager -U your_user < services/backend/data/feed_sources.sql

# Or using Docker:
docker exec -i taskmanager-postgres psql -U postgres -d taskmanager < services/backend/data/feed_sources.sql
```

The SQL import uses `ON CONFLICT (url) DO NOTHING` so it's safe to run multiple times.

### Option 3: Using JSON with a Custom Script

```python
import asyncio
import json
from app.db.database import async_session_maker
from app.models.feed_source import FeedSource

async def import_feeds():
    with open('data/feed_sources.json') as f:
        feeds = json.load(f)

    async with async_session_maker() as db:
        for feed_data in feeds:
            # Check if exists
            from sqlalchemy import select
            stmt = select(FeedSource).where(FeedSource.url == feed_data['url'])
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                continue

            # Create new feed
            feed = FeedSource(**feed_data)
            db.add(feed)

        await db.commit()

asyncio.run(import_feeds())
```

## Feed Sources Included

**Research Papers (3):**
- ArXiv CS.CR (Cryptography and Security)
- ArXiv CS.AI (Artificial Intelligence)
- ArXiv CS.LG (Machine Learning)

**Security Blogs (4):**
- OWASP Blog
- Trail of Bits Blog
- NIST Cybersecurity Insights
- Schneier on Security

**AI Research Blogs (5):**
- Google AI Blog
- OpenAI Blog
- Anthropic Blog
- DeepMind Blog
- The Gradient

Total: 12 curated AI/LLM security sources
