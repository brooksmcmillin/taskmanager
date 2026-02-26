"""Tests for PostgresTokenStorage timezone handling.

Asyncpg returns timezone-aware datetimes from TIMESTAMPTZ columns.
These tests verify that PostgresTokenStorage consistently uses
timezone-aware datetimes so comparisons don't raise TypeError.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_auth_framework.storage.postgres import PostgresTokenStorage


def _make_storage() -> PostgresTokenStorage:
    """Create a PostgresTokenStorage with a mocked pool."""
    storage = PostgresTokenStorage(database_url="postgresql://test:test@localhost/test")
    storage._pool = MagicMock()
    return storage


def _mock_conn(fetchrow_return: dict | None = None, execute_return: str = "DELETE 0") -> MagicMock:
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.execute = AsyncMock(return_value=execute_return)
    return conn


def _patch_pool(storage: PostgresTokenStorage, conn: MagicMock) -> None:
    """Patch storage._pool.acquire() to yield the mock connection."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    storage._pool.acquire = MagicMock(return_value=ctx)


class TestStoreTokenTimezone:
    """Verify store_token passes timezone-aware datetimes to the database."""

    @pytest.mark.asyncio
    async def test_store_token_passes_aware_datetime(self) -> None:
        storage = _make_storage()
        conn = _mock_conn()
        _patch_pool(storage, conn)

        expires_at = int(datetime.now(timezone.utc).timestamp()) + 3600

        await storage.store_token(
            token="test_token",
            client_id="client1",
            scopes=["read"],
            expires_at=expires_at,
        )

        call_args = conn.execute.call_args
        expires_datetime = call_args[0][5]  # 6th positional arg
        assert expires_datetime.tzinfo is not None, (
            "expires_at datetime passed to DB must be timezone-aware"
        )
        assert expires_datetime.tzinfo == timezone.utc

    @pytest.mark.asyncio
    async def test_store_refresh_token_passes_aware_datetime(self) -> None:
        storage = _make_storage()
        conn = _mock_conn()
        _patch_pool(storage, conn)

        expires_at = int(datetime.now(timezone.utc).timestamp()) + 86400

        await storage.store_refresh_token(
            refresh_token="test_refresh",
            client_id="client1",
            scopes=["read"],
            expires_at=expires_at,
        )

        call_args = conn.execute.call_args
        expires_datetime = call_args[0][5]
        assert expires_datetime.tzinfo is not None, (
            "expires_at datetime passed to DB must be timezone-aware"
        )
        assert expires_datetime.tzinfo == timezone.utc


class TestLoadTokenTimezone:
    """Verify load_token handles timezone-aware datetimes from asyncpg.

    Asyncpg returns timezone-aware datetimes for TIMESTAMPTZ columns.
    These tests simulate that behavior and verify no TypeError is raised.
    """

    @pytest.mark.asyncio
    async def test_load_valid_token_with_aware_datetime(self) -> None:
        """Loading a non-expired token should succeed when DB returns aware datetimes."""
        storage = _make_storage()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        created = datetime.now(timezone.utc) - timedelta(hours=1)
        row = {
            "token": "test_token",
            "client_id": "client1",
            "scopes": "read write",
            "resource": None,
            "expires_at": future,
            "created_at": created,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_token("test_token")

        assert result is not None
        assert result["token"] == "test_token"
        assert result["scopes"] == ["read", "write"]

    @pytest.mark.asyncio
    async def test_load_expired_token_with_aware_datetime(self) -> None:
        """Loading an expired token should return None without raising TypeError."""
        storage = _make_storage()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        created = datetime.now(timezone.utc) - timedelta(hours=2)
        row = {
            "token": "expired_token",
            "client_id": "client1",
            "scopes": "read",
            "resource": None,
            "expires_at": past,
            "created_at": created,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_token("expired_token")

        assert result is None
        conn.execute.assert_called_once()  # delete was called

    @pytest.mark.asyncio
    async def test_load_token_not_found(self) -> None:
        storage = _make_storage()
        conn = _mock_conn(fetchrow_return=None)
        _patch_pool(storage, conn)

        result = await storage.load_token("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_load_token_naive_datetime_would_fail(self) -> None:
        """Demonstrate that mixing naive DB datetimes with aware now() raises TypeError.

        This is the exact bug that was fixed. If someone reverts the fix in
        load_token to use datetime.utcnow() (naive), this test will catch it.
        """
        storage = _make_storage()
        # Simulate asyncpg returning a timezone-AWARE datetime (as TIMESTAMPTZ does)
        future_aware = datetime.now(timezone.utc) + timedelta(hours=1)
        row = {
            "token": "test_token",
            "client_id": "client1",
            "scopes": "read",
            "resource": None,
            "expires_at": future_aware,
            "created_at": datetime.now(timezone.utc),
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        # This must NOT raise TypeError
        result = await storage.load_token("test_token")
        assert result is not None


class TestLoadRefreshTokenTimezone:
    """Same timezone tests for refresh tokens."""

    @pytest.mark.asyncio
    async def test_load_valid_refresh_token_with_aware_datetime(self) -> None:
        storage = _make_storage()
        future = datetime.now(timezone.utc) + timedelta(days=7)
        created = datetime.now(timezone.utc) - timedelta(hours=1)
        row = {
            "token": "refresh_token",
            "client_id": "client1",
            "scopes": "read write",
            "resource": "https://example.com",
            "expires_at": future,
            "created_at": created,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_refresh_token("refresh_token")

        assert result is not None
        assert result["token"] == "refresh_token"
        assert result["resource"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_load_expired_refresh_token_with_aware_datetime(self) -> None:
        storage = _make_storage()
        past = datetime.now(timezone.utc) - timedelta(days=1)
        created = datetime.now(timezone.utc) - timedelta(days=8)
        row = {
            "token": "expired_refresh",
            "client_id": "client1",
            "scopes": "read",
            "resource": None,
            "expires_at": past,
            "created_at": created,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_refresh_token("expired_refresh")

        assert result is None
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_refresh_token_not_found(self) -> None:
        storage = _make_storage()
        conn = _mock_conn(fetchrow_return=None)
        _patch_pool(storage, conn)

        result = await storage.load_refresh_token("nonexistent")

        assert result is None


class TestCleanupTimezone:
    """Verify cleanup methods pass timezone-aware datetimes to SQL queries."""

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_uses_aware_datetime(self) -> None:
        storage = _make_storage()
        conn = _mock_conn(execute_return="DELETE 3")
        _patch_pool(storage, conn)

        count = await storage.cleanup_expired_tokens()

        assert count == 3
        call_args = conn.execute.call_args
        now_arg = call_args[0][1]
        assert now_arg.tzinfo is not None, (
            "now datetime passed to cleanup query must be timezone-aware"
        )

    @pytest.mark.asyncio
    async def test_cleanup_expired_refresh_tokens_uses_aware_datetime(self) -> None:
        storage = _make_storage()
        conn = _mock_conn(execute_return="DELETE 5")
        _patch_pool(storage, conn)

        count = await storage.cleanup_expired_refresh_tokens()

        assert count == 5
        call_args = conn.execute.call_args
        now_arg = call_args[0][1]
        assert now_arg.tzinfo is not None, (
            "now datetime passed to cleanup query must be timezone-aware"
        )


class TestLoadTokenReturnFormat:
    """Verify load methods return correct data shapes."""

    @pytest.mark.asyncio
    async def test_load_token_returns_unix_timestamps(self) -> None:
        storage = _make_storage()
        future = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        created = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        row = {
            "token": "tok",
            "client_id": "c1",
            "scopes": "read",
            "resource": None,
            "expires_at": future,
            "created_at": created,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_token("tok")

        assert result is not None
        assert isinstance(result["expires_at"], int)
        assert isinstance(result["created_at"], int)
        assert result["expires_at"] == int(future.timestamp())
        assert result["created_at"] == int(created.timestamp())

    @pytest.mark.asyncio
    async def test_load_token_empty_scopes(self) -> None:
        storage = _make_storage()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        row = {
            "token": "tok",
            "client_id": "c1",
            "scopes": "",
            "resource": None,
            "expires_at": future,
            "created_at": datetime.now(timezone.utc),
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_token("tok")

        assert result is not None
        assert result["scopes"] == []

    @pytest.mark.asyncio
    async def test_load_token_null_created_at(self) -> None:
        storage = _make_storage()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        row = {
            "token": "tok",
            "client_id": "c1",
            "scopes": "read",
            "resource": None,
            "expires_at": future,
            "created_at": None,
        }
        conn = _mock_conn(fetchrow_return=row)
        _patch_pool(storage, conn)

        result = await storage.load_token("tok")

        assert result is not None
        assert result["created_at"] is None
