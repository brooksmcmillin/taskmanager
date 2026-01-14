"""Rate limiting utilities."""

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from app.config import settings
from app.core.errors import errors


class RateLimiter:
    """In-memory rate limiter for login attempts.

    Thread-safe implementation using a simple sliding window approach.
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        window_ms: int | None = None,
    ) -> None:
        self.max_attempts = max_attempts or settings.login_max_attempts
        self.window_ms = window_ms or settings.login_window_ms
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def _cleanup_old_attempts(self, key: str, now: float) -> None:
        """Remove attempts outside the window."""
        window_start = now - (self.window_ms / 1000)
        self._attempts[key] = [
            ts for ts in self._attempts[key] if ts > window_start
        ]

    def check(self, key: str) -> None:
        """Check if key is rate limited. Raises ApiError if limited."""
        now = datetime.now(timezone.utc).timestamp()

        with self._lock:
            self._cleanup_old_attempts(key, now)
            if len(self._attempts[key]) >= self.max_attempts:
                retry_after = int(self.window_ms / 1000)
                raise errors.rate_limited(retry_after)

    def record(self, key: str) -> None:
        """Record an attempt for the key."""
        now = datetime.now(timezone.utc).timestamp()

        with self._lock:
            self._cleanup_old_attempts(key, now)
            self._attempts[key].append(now)

    def reset(self, key: str) -> None:
        """Reset attempts for a key (e.g., after successful login)."""
        with self._lock:
            self._attempts.pop(key, None)

    def cleanup(self) -> None:
        """Remove all expired entries."""
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - (self.window_ms / 1000)

        with self._lock:
            keys_to_remove = []
            for key, attempts in self._attempts.items():
                self._attempts[key] = [ts for ts in attempts if ts > window_start]
                if not self._attempts[key]:
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self._attempts[key]


# Global rate limiter for login attempts
login_rate_limiter = RateLimiter()
