"""Rate limiting utilities backed by PostgreSQL for multi-worker support."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, type_coerce
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import errors
from app.models.shared_state import SharedState

NAMESPACE = "rate_limit"


class RateLimiter:
    """PostgreSQL-backed rate limiter for login attempts.

    Uses a sliding window approach with attempt timestamps stored in
    the shared_state table. Safe for multi-worker deployments.
    """

    def __init__(
        self,
        max_attempts: int | None = None,
        window_ms: int | None = None,
        name: str = "default",
    ) -> None:
        self.max_attempts = max_attempts or settings.login_max_attempts
        self.window_ms = window_ms or settings.login_window_ms
        self.name = name

    def _db_key(self, key: str) -> str:
        """Build the database key combining limiter name and user key."""
        return f"{self.name}:{key}"

    def _window_start(self) -> float:
        """Return the timestamp marking the start of the current window."""
        now = datetime.now(UTC).timestamp()
        return now - (self.window_ms / 1000)

    def _expiry(self) -> datetime:
        """Return the expiration datetime for new entries."""
        return datetime.now(UTC) + timedelta(milliseconds=self.window_ms)

    def _filter_attempts(self, attempts: list[float]) -> list[float]:
        """Filter attempts to only those within the current window."""
        window_start = self._window_start()
        return [ts for ts in attempts if ts > window_start]

    async def check(self, key: str, db: AsyncSession | None = None) -> None:
        """Check if key is rate limited. Raises ApiError if limited.

        Args:
            key: The rate limit key (e.g., email address or IP).
            db: Optional database session. If not provided, creates one
                internally using the session factory.
        """
        if db is not None:
            await self._check_impl(key, db)
        else:
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                await self._check_impl(key, session)
                await session.commit()

    async def _check_impl(self, key: str, db: AsyncSession) -> None:
        """Internal check implementation."""
        db_key = self._db_key(key)
        now = datetime.now(UTC)

        result = await db.execute(
            select(SharedState.value).where(
                SharedState.namespace == NAMESPACE,
                SharedState.key == db_key,
                SharedState.expires_at > now,
            )
        )
        row = result.scalar_one_or_none()

        if row is not None:
            attempts = self._filter_attempts(row.get("attempts", []))
            if len(attempts) >= self.max_attempts:
                retry_after = int(self.window_ms / 1000)
                raise errors.rate_limited(retry_after)

    async def record(self, key: str, db: AsyncSession | None = None) -> None:
        """Record an attempt for the key.

        Args:
            key: The rate limit key.
            db: Optional database session.
        """
        if db is not None:
            await self._record_impl(key, db)
        else:
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                await self._record_impl(key, session)
                await session.commit()

    async def _record_impl(self, key: str, db: AsyncSession) -> None:
        """Internal record implementation.

        Uses a single atomic upsert to append the new timestamp to the
        attempts array. On conflict (existing key), the append happens
        entirely in SQL using JSONB concatenation, so concurrent workers
        cannot lose each other's writes.

        Note: expired timestamps are filtered out at check time rather
        than at record time, keeping the atomic append simple. The cleanup()
        method can be called periodically to remove fully expired entries.
        """
        db_key = self._db_key(key)
        now = datetime.now(UTC)
        now_ts = now.timestamp()
        new_attempt_json = type_coerce(func.jsonb_build_array(now_ts), JSONB)

        # Atomic upsert: INSERT new entry or append to existing array
        # The ON CONFLICT clause uses the *existing row's* value column
        # (via excluded/shared_state reference), so concurrent upserts
        # each atomically append their own timestamp.
        stmt = (
            insert(SharedState)
            .values(
                namespace=NAMESPACE,
                key=db_key,
                value=func.jsonb_build_object("attempts", new_attempt_json),
                expires_at=self._expiry(),
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["namespace", "key"],
                set_={
                    "value": func.jsonb_build_object(
                        "attempts",
                        SharedState.value["attempts"].concat(new_attempt_json),
                    ),
                    "expires_at": self._expiry(),
                    "updated_at": now,
                },
            )
        )
        await db.execute(stmt)

    async def reset(self, key: str, db: AsyncSession | None = None) -> None:
        """Reset attempts for a key (e.g., after successful login).

        Args:
            key: The rate limit key.
            db: Optional database session.
        """
        if db is not None:
            await self._reset_impl(key, db)
        else:
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                await self._reset_impl(key, session)
                await session.commit()

    async def _reset_impl(self, key: str, db: AsyncSession) -> None:
        """Internal reset implementation."""
        db_key = self._db_key(key)
        await db.execute(
            delete(SharedState).where(
                SharedState.namespace == NAMESPACE,
                SharedState.key == db_key,
            )
        )

    async def cleanup(self, db: AsyncSession | None = None) -> None:
        """Remove all expired entries for this rate limiter.

        Args:
            db: Optional database session.
        """
        if db is not None:
            await self._cleanup_impl(db)
        else:
            from app.db.database import async_session_maker

            async with async_session_maker() as session:
                await self._cleanup_impl(session)
                await session.commit()

    async def _cleanup_impl(self, db: AsyncSession) -> None:
        """Internal cleanup implementation."""
        now = datetime.now(UTC)
        await db.execute(
            delete(SharedState).where(
                SharedState.namespace == NAMESPACE,
                SharedState.key.like(f"{self.name}:%"),
                SharedState.expires_at <= now,
            )
        )


# Global rate limiter for login attempts
login_rate_limiter = RateLimiter(name="login")

# Rate limiter for API key authentication attempts
# More restrictive: 20 attempts per minute to prevent brute force
api_key_rate_limiter = RateLimiter(max_attempts=20, window_ms=60000, name="api_key")
