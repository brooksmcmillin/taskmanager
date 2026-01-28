"""Test manual news fetch."""

import asyncio

from app.services.news_fetcher import fetch_all_feeds

if __name__ == "__main__":
    print("Testing news fetch...\n")
    results = asyncio.run(fetch_all_feeds())
    print(f"\n✓ Fetch results: {results}")
    print("\nDone!")
