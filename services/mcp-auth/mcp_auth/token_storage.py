"""
Database-backed token storage for MCP access tokens.

This module provides persistent storage for MCP access tokens using PostgreSQL,
ensuring tokens survive server restarts.
"""

import logging
import os
from datetime import datetime
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class TokenStorage:
    """Database-backed storage for MCP access tokens."""

    def __init__(self, database_url: str | None = None):
        """
        Initialize token storage.

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
        """
        Store an access token in the database.

        Args:
            token: The access token string
            client_id: OAuth client ID
            scopes: List of granted scopes
            expires_at: Unix timestamp when token expires
            resource: Optional RFC 8707 resource binding
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        # Use naive datetime for PostgreSQL TIMESTAMP column (without timezone)
        expires_datetime = datetime.utcfromtimestamp(expires_at)
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
        """
        Load an access token from the database.

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

        # Check if expired (using naive UTC datetimes for PostgreSQL TIMESTAMP)
        expires_at = row["expires_at"]
        now = datetime.utcnow()
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
        """
        Delete a token from the database.

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
        """
        Remove all expired tokens from the database.

        Returns:
            Number of tokens removed
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        # Use naive UTC datetime for PostgreSQL TIMESTAMP column
        now = datetime.utcnow()
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
        """
        Get the total number of tokens in storage.

        Returns:
            Number of tokens stored
        """
        if not self._pool:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) as count FROM mcp_access_tokens")
        return row["count"] if row else 0


# Global token storage instance
_token_storage: TokenStorage | None = None


async def get_token_storage() -> TokenStorage:
    """
    Get the global token storage instance, initializing if needed.

    Returns:
        Initialized TokenStorage instance
    """
    global _token_storage
    if _token_storage is None:
        _token_storage = TokenStorage()
        await _token_storage.initialize()
    return _token_storage


async def close_token_storage() -> None:
    """Close the global token storage instance."""
    global _token_storage
    if _token_storage:
        await _token_storage.close()
        _token_storage = None
