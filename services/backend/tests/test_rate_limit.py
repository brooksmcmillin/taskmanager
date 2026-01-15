"""Tests for rate limiting logic."""

import time

import pytest

from app.core.errors import ApiError
from app.core.rate_limit import RateLimiter


def test_rate_limiter_allows_within_limit():
    """Test that rate limiter allows requests within the limit."""
    limiter = RateLimiter(max_attempts=3, window_ms=1000)

    # Should allow first 3 attempts
    limiter.check("test_user")
    limiter.record("test_user")

    limiter.check("test_user")
    limiter.record("test_user")

    limiter.check("test_user")
    limiter.record("test_user")


def test_rate_limiter_blocks_when_exceeded():
    """Test that rate limiter blocks when limit is exceeded."""
    limiter = RateLimiter(max_attempts=3, window_ms=1000)

    # Record 3 attempts
    for _ in range(3):
        limiter.record("test_user")

    # 4th check should raise error
    with pytest.raises(ApiError) as exc_info:
        limiter.check("test_user")

    assert exc_info.value.status_code == 429


def test_rate_limiter_reset_clears_attempts():
    """Test that reset clears attempts for a key."""
    limiter = RateLimiter(max_attempts=3, window_ms=1000)

    # Record 3 attempts
    for _ in range(3):
        limiter.record("test_user")

    # Reset the user
    limiter.reset("test_user")

    # Should allow requests again
    limiter.check("test_user")
    limiter.record("test_user")


def test_rate_limiter_per_key_isolation():
    """Test that rate limiting is per key."""
    limiter = RateLimiter(max_attempts=3, window_ms=1000)

    # Max out user1
    for _ in range(3):
        limiter.record("user1")

    # user1 should be blocked
    with pytest.raises(ApiError):
        limiter.check("user1")

    # user2 should still be allowed
    limiter.check("user2")
    limiter.record("user2")


def test_rate_limiter_sliding_window():
    """Test that old attempts expire from the window."""
    limiter = RateLimiter(max_attempts=3, window_ms=500)  # 500ms window

    # Record 2 attempts
    limiter.record("test_user")
    limiter.record("test_user")

    # Wait for window to expire
    time.sleep(0.6)

    # Should allow new attempts since old ones expired
    limiter.check("test_user")
    limiter.record("test_user")
    limiter.check("test_user")
    limiter.record("test_user")
    limiter.check("test_user")


def test_rate_limiter_cleanup():
    """Test that cleanup removes expired entries."""
    limiter = RateLimiter(max_attempts=3, window_ms=100)

    # Record attempts for multiple users
    limiter.record("user1")
    limiter.record("user2")
    limiter.record("user3")

    assert len(limiter._attempts) == 3

    # Wait for window to expire
    time.sleep(0.2)

    # Cleanup should remove all entries
    limiter.cleanup()

    assert len(limiter._attempts) == 0
