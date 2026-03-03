"""Background task scheduler using APScheduler."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.services.article_summarizer import generate_article_summaries
from app.services.news_fetcher import fetch_all_feeds

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the background task scheduler."""
    logger.info("Starting background task scheduler")

    # Schedule news fetching every 6 hours
    scheduler.add_job(
        fetch_all_feeds,
        trigger=IntervalTrigger(hours=6),
        id="fetch_news_feeds",
        name="Fetch AI/LLM security news feeds",
        replace_existing=True,
    )

    # Schedule article summarization every 6 hours (5 min offset after feed fetch)
    scheduler.add_job(
        generate_article_summaries,
        trigger=IntervalTrigger(hours=6, minutes=5),
        id="generate_article_summaries",
        name="Generate AI summaries for new articles",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Background task scheduler started")


def stop_scheduler() -> None:
    """Stop the background task scheduler."""
    logger.info("Stopping background task scheduler")
    scheduler.shutdown()
    logger.info("Background task scheduler stopped")
