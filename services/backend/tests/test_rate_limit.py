"""Tests for rate limiting logic (PostgreSQL-backed)."""

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.rate_limit import NAMESPACE, RateLimiter
from app.models.shared_state import SharedState


@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit(db_session: AsyncSession):
    """Test that rate limiter allows requests within the limit."""
    limiter = RateLimiter(max_attempts=3, window_ms=1000, name="test_allow")

    # Should allow first 3 attempts
    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)

    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)

    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)


@pytest.mark.asyncio
async def test_rate_limiter_blocks_when_exceeded(db_session: AsyncSession):
    """Test that rate limiter blocks when limit is exceeded."""
    limiter = RateLimiter(max_attempts=3, window_ms=5000, name="test_block")

    # Record 3 attempts
    for _ in range(3):
        await limiter.record("test_user", db_session)
    await db_session.flush()

    # 4th check should raise error
    with pytest.raises(ApiError) as exc_info:
        await limiter.check("test_user", db_session)

    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limiter_reset_clears_attempts(db_session: AsyncSession):
    """Test that reset clears attempts for a key."""
    limiter = RateLimiter(max_attempts=3, window_ms=5000, name="test_reset")

    # Record 3 attempts
    for _ in range(3):
        await limiter.record("test_user", db_session)
    await db_session.flush()

    # Reset the user
    await limiter.reset("test_user", db_session)
    await db_session.flush()

    # Should allow requests again
    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)


@pytest.mark.asyncio
async def test_rate_limiter_per_key_isolation(db_session: AsyncSession):
    """Test that rate limiting is per key."""
    limiter = RateLimiter(max_attempts=3, window_ms=5000, name="test_iso")

    # Max out user1
    for _ in range(3):
        await limiter.record("user1", db_session)
    await db_session.flush()

    # user1 should be blocked
    with pytest.raises(ApiError):
        await limiter.check("user1", db_session)

    # user2 should still be allowed
    await limiter.check("user2", db_session)
    await limiter.record("user2", db_session)


@pytest.mark.asyncio
async def test_rate_limiter_sliding_window(db_session: AsyncSession):
    """Test that old attempts expire from the window."""
    limiter = RateLimiter(max_attempts=3, window_ms=500, name="test_window")

    # Record 2 attempts
    await limiter.record("test_user", db_session)
    await limiter.record("test_user", db_session)
    await db_session.flush()

    # Wait for window to expire
    await asyncio.sleep(0.6)

    # Should allow new attempts since old ones expired
    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)
    await limiter.check("test_user", db_session)
    await limiter.record("test_user", db_session)
    await limiter.check("test_user", db_session)


@pytest.mark.asyncio
async def test_rate_limiter_cleanup(db_session: AsyncSession):
    """Test that cleanup removes expired entries."""
    limiter = RateLimiter(max_attempts=3, window_ms=100, name="test_cleanup")

    # Record attempts for multiple users
    await limiter.record("user1", db_session)
    await limiter.record("user2", db_session)
    await limiter.record("user3", db_session)
    await db_session.flush()

    # Verify entries exist
    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == NAMESPACE,
            SharedState.key.like("test_cleanup:%"),
        )
    )
    entries = result.scalars().all()
    assert len(entries) == 3

    # Wait for window to expire
    await asyncio.sleep(0.2)

    # Cleanup should remove all entries
    await limiter.cleanup(db_session)
    await db_session.flush()

    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == NAMESPACE,
            SharedState.key.like("test_cleanup:%"),
        )
    )
    entries = result.scalars().all()
    assert len(entries) == 0


@pytest.mark.asyncio
async def test_rate_limiter_stores_in_database(db_session: AsyncSession):
    """Test that rate limiter data is persisted in the database."""
    limiter = RateLimiter(max_attempts=5, window_ms=5000, name="test_persist")

    await limiter.record("persist_key", db_session)
    await db_session.flush()

    # Verify the entry exists in the database
    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == NAMESPACE,
            SharedState.key == "test_persist:persist_key",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert "attempts" in entry.value
    assert len(entry.value["attempts"]) == 1


@pytest.mark.asyncio
async def test_rate_limiter_accumulates_multiple_records(db_session: AsyncSession):
    """Test that multiple records accumulate correctly."""
    limiter = RateLimiter(max_attempts=10, window_ms=5000, name="test_accum")

    for _ in range(5):
        await limiter.record("accum_key", db_session)
    await db_session.flush()

    # Verify all 5 attempts are stored
    result = await db_session.execute(
        select(SharedState).where(
            SharedState.namespace == NAMESPACE,
            SharedState.key == "test_accum:accum_key",
        )
    )
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert len(entry.value["attempts"]) == 5
