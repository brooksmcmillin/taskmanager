"""PostgreSQL-backed token storage implementation."""

import logging
import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

from mcp_auth_framework.storage.base import TokenStorage

logger = logging.getLogger(__name__)


class PostgresTokenStorage(TokenStorage):
    """Database-backed storage for MCP access tokens using PostgreSQL."""

    def __init__(self, database_url: str | None = None):
        """Initialize token storage.

        Args:
            database_url: PostgreSQL connection URL. If not provided,
                         will be read from DATABASE_URL environment variable.
        """
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        self._pool: asyncpg.Pool | None = None

    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required for token storage")

        logger.info("Initializing database connection pool for token storage")
        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("Database connection pool initialized")

    async def close(self) -> None:
        """Close the database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database connection pool closed")

    async def store_token(
        self,
        token: str,
        client_id: str,
        scopes: list[str],
        expires_at: int,
        resource: str | None = None,
    ) -> None:
        """Store an access token in the database.

        Args:
            token: The access token string
            client_id: OAuth client ID
            scopes: List of granted scopes
            expires_at: Unix timestamp when token expires
            resource: Optional RFC 8707 resource binding
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        expires_datetime = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        scopes_str = " ".join(scopes)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO mcp_access_tokens (token, client_id, scopes, resource, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (token) DO UPDATE SET
                    client_id = EXCLUDED.client_id,
                    scopes = EXCLUDED.scopes,
                    resource = EXCLUDED.resource,
                    expires_at = EXCLUDED.expires_at
                """,
                token,
                client_id,
                scopes_str,
                resource,
                expires_datetime,
            )
        logger.debug(f"Stored token {token[:20]}... for client {client_id}")

    async def load_token(self, token: str) -> dict[str, Any] | None:
        """Load an access token from the database.

        Args:
            token: The access token string to look up

        Returns:
            Token data dict if found and not expired, None otherwise
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT token, client_id, scopes, resource, expires_at, created_at
                FROM mcp_access_tokens
                WHERE token = $1
                """,
                token,
            )

        if not row:
            logger.debug(f"Token {token[:20]}... not found in database")
            return None

        expires_at = row["expires_at"]
        now = datetime.now(timezone.utc)
        if expires_at < now:
            logger.debug(f"Token {token[:20]}... has expired")
            # Clean up expired token
            await self.delete_token(token)
            return None

        return {
            "token": row["token"],
            "client_id": row["client_id"],
            "scopes": row["scopes"].split() if row["scopes"] else [],
            "resource": row["resource"],
            "expires_at": int(expires_at.timestamp()),
            "created_at": int(row["created_at"].timestamp()) if row["created_at"] else None,
        }

    async def delete_token(self, token: str) -> None:
        """Delete a token from the database.

        Args:
            token: The access token string to delete
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM mcp_access_tokens WHERE token = $1",
                token,
            )
        logger.debug(f"Deleted token {token[:20]}...")

    async def cleanup_expired_tokens(self) -> int:
        """Remove all expired tokens from the database.

        Returns:
            Number of tokens removed
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM mcp_access_tokens WHERE expires_at < $1",
                now,
            )
        # Parse the DELETE count from result string like "DELETE 5"
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(f"Cleaned up {count} expired tokens")
        return count

    async def get_token_count(self) -> int:
        """Get the total number of tokens in storage.

        Returns:
            Number of tokens stored
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM mcp_access_tokens")
        return row["count"] if row else 0

    async def store_refresh_token(
        self,
        refresh_token: str,
        client_id: str,
        scopes: list[str],
        expires_at: int,
        resource: str | None = None,
    ) -> None:
        """Store a refresh token in the database.

        Args:
            refresh_token: The refresh token string
            client_id: OAuth client ID
            scopes: List of granted scopes
            expires_at: Unix timestamp when token expires
            resource: Optional RFC 8707 resource binding
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        expires_datetime = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        scopes_str = " ".join(scopes)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO mcp_refresh_tokens (token, client_id, scopes, resource, expires_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (token) DO UPDATE SET
                    client_id = EXCLUDED.client_id,
                    scopes = EXCLUDED.scopes,
                    resource = EXCLUDED.resource,
                    expires_at = EXCLUDED.expires_at
                """,
                refresh_token,
                client_id,
                scopes_str,
                resource,
                expires_datetime,
            )
        logger.debug(f"Stored refresh token {refresh_token[:20]}... for client {client_id}")

    async def load_refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Load a refresh token from the database.

        Args:
            refresh_token: The refresh token string to look up

        Returns:
            Token data dict if found and not expired, None otherwise
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT token, client_id, scopes, resource, expires_at, created_at
                FROM mcp_refresh_tokens
                WHERE token = $1
                """,
                refresh_token,
            )

        if not row:
            logger.debug(f"Refresh token {refresh_token[:20]}... not found in database")
            return None

        # Check if expired
        expires_at = row["expires_at"]
        now = datetime.now(timezone.utc)
        if expires_at < now:
            logger.debug(f"Refresh token {refresh_token[:20]}... has expired")
            await self.delete_refresh_token(refresh_token)
            return None

        return {
            "token": row["token"],
            "client_id": row["client_id"],
            "scopes": row["scopes"].split() if row["scopes"] else [],
            "resource": row["resource"],
            "expires_at": int(expires_at.timestamp()),
            "created_at": int(row["created_at"].timestamp()) if row["created_at"] else None,
        }

    async def delete_refresh_token(self, refresh_token: str) -> None:
        """Delete a refresh token from the database.

        Args:
            refresh_token: The refresh token string to delete
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM mcp_refresh_tokens WHERE token = $1",
                refresh_token,
            )
        logger.debug(f"Deleted refresh token {refresh_token[:20]}...")

    async def cleanup_expired_refresh_tokens(self) -> int:
        """Remove all expired refresh tokens from the database.

        Returns:
            Number of tokens removed
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        now = datetime.now(timezone.utc)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM mcp_refresh_tokens WHERE expires_at < $1",
                now,
            )
        count = int(result.split()[-1]) if result else 0
        if count > 0:
            logger.info(f"Cleaned up {count} expired refresh tokens")
        return count
