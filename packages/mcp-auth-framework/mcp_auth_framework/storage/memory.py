"""In-memory token storage implementation for testing."""

import logging
import time
from typing import Any

from mcp_auth_framework.storage.base import TokenStorage

logger = logging.getLogger(__name__)


class MemoryTokenStorage(TokenStorage):
    """In-memory token storage for testing and development.

    This implementation stores tokens in memory and does not persist them
    across restarts. Suitable for testing and development only.
    """

    def __init__(self) -> None:
        """Initialize in-memory token storage."""
        self._access_tokens: dict[str, dict[str, Any]] = {}
        self._refresh_tokens: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the storage (no-op for memory storage)."""
        logger.info("Initializing in-memory token storage")
        self._initialized = True

    async def close(self) -> None:
        """Close the storage and clear all tokens."""
        logger.info("Closing in-memory token storage")
        self._access_tokens.clear()
        self._refresh_tokens.clear()
        self._initialized = False

    async def store_token(
        self,
        token: str,
        client_id: str,
        scopes: list[str],
        expires_at: int,
        resource: str | None = None,
    ) -> None:
        """Store an access token in memory.

        Args:
            token: The access token string
            client_id: OAuth client ID
            scopes: List of granted scopes
            expires_at: Unix timestamp when token expires
            resource: Optional RFC 8707 resource binding
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        self._access_tokens[token] = {
            "token": token,
            "client_id": client_id,
            "scopes": scopes.copy(),
            "resource": resource,
            "expires_at": expires_at,
            "created_at": int(time.time()),
        }
        logger.debug(f"Stored token {token[:20]}... for client {client_id}")

    async def load_token(self, token: str) -> dict[str, Any] | None:
        """Load an access token from memory.

        Args:
            token: The access token string to look up

        Returns:
            Token data dict if found and not expired, None otherwise
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        token_data = self._access_tokens.get(token)
        if not token_data:
            logger.debug(f"Token {token[:20]}... not found in memory")
            return None

        # Check if expired
        now = int(time.time())
        if token_data["expires_at"] < now:
            logger.debug(f"Token {token[:20]}... has expired")
            await self.delete_token(token)
            return None

        return token_data.copy()

    async def delete_token(self, token: str) -> None:
        """Delete a token from memory.

        Args:
            token: The access token string to delete
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        if token in self._access_tokens:
            del self._access_tokens[token]
            logger.debug(f"Deleted token {token[:20]}...")

    async def cleanup_expired_tokens(self) -> int:
        """Remove all expired access tokens from memory.

        Returns:
            Number of tokens removed
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        now = int(time.time())
        expired_tokens = [
            token for token, data in self._access_tokens.items() if data["expires_at"] < now
        ]

        for token in expired_tokens:
            del self._access_tokens[token]

        count = len(expired_tokens)
        if count > 0:
            logger.info(f"Cleaned up {count} expired tokens")
        return count

    async def get_token_count(self) -> int:
        """Get the total number of access tokens in storage.

        Returns:
            Number of tokens stored
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        return len(self._access_tokens)

    async def store_refresh_token(
        self,
        refresh_token: str,
        client_id: str,
        scopes: list[str],
        expires_at: int,
        resource: str | None = None,
    ) -> None:
        """Store a refresh token in memory.

        Args:
            refresh_token: The refresh token string
            client_id: OAuth client ID
            scopes: List of granted scopes
            expires_at: Unix timestamp when token expires
            resource: Optional RFC 8707 resource binding
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        self._refresh_tokens[refresh_token] = {
            "token": refresh_token,
            "client_id": client_id,
            "scopes": scopes.copy(),
            "resource": resource,
            "expires_at": expires_at,
            "created_at": int(time.time()),
        }
        logger.debug(f"Stored refresh token {refresh_token[:20]}... for client {client_id}")

    async def load_refresh_token(self, refresh_token: str) -> dict[str, Any] | None:
        """Load a refresh token from memory.

        Args:
            refresh_token: The refresh token string to look up

        Returns:
            Token data dict if found and not expired, None otherwise
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        token_data = self._refresh_tokens.get(refresh_token)
        if not token_data:
            logger.debug(f"Refresh token {refresh_token[:20]}... not found in memory")
            return None

        # Check if expired
        now = int(time.time())
        if token_data["expires_at"] < now:
            logger.debug(f"Refresh token {refresh_token[:20]}... has expired")
            await self.delete_refresh_token(refresh_token)
            return None

        return token_data.copy()

    async def delete_refresh_token(self, refresh_token: str) -> None:
        """Delete a refresh token from memory.

        Args:
            refresh_token: The refresh token string to delete
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        if refresh_token in self._refresh_tokens:
            del self._refresh_tokens[refresh_token]
            logger.debug(f"Deleted refresh token {refresh_token[:20]}...")

    async def cleanup_expired_refresh_tokens(self) -> int:
        """Remove all expired refresh tokens from memory.

        Returns:
            Number of tokens removed
        """
        if not self._initialized:
            raise RuntimeError("Token storage not initialized. Call initialize() first.")

        now = int(time.time())
        expired_tokens = [
            token for token, data in self._refresh_tokens.items() if data["expires_at"] < now
        ]

        for token in expired_tokens:
            del self._refresh_tokens[token]

        count = len(expired_tokens)
        if count > 0:
            logger.info(f"Cleaned up {count} expired refresh tokens")
        return count
