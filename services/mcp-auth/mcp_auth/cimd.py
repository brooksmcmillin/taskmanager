"""
Client ID Metadata Document (CIMD) Support

This module implements support for OAuth Client ID Metadata Documents as specified in:
- draft-ietf-oauth-client-id-metadata-document-00

CIMD allows OAuth clients to identify themselves using a URL as the client_id.
The URL points to a JSON metadata document containing the client's configuration.

Key features:
- URL-based client identification (no pre-registration required)
- Metadata fetched on-demand from client-controlled URLs
- Caching to reduce network requests
- Support for public clients (PKCE) and confidential clients (private_key_jwt)
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import aiohttp
from mcp.shared.auth import OAuthClientInformationFull

logger = logging.getLogger(__name__)

# CIMD specification constants
CIMD_MAX_DOCUMENT_SIZE = 10 * 1024  # 10KB max document size
CIMD_CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours cache TTL
CIMD_FETCH_TIMEOUT_SECONDS = 10  # 10 second timeout for fetching metadata
CIMD_CONNECT_TIMEOUT_SECONDS = 5  # 5 second connection timeout

# Allowed authentication methods for CIMD clients
# Note: client_secret_* methods are NOT allowed per the spec since there's no way
# to establish a shared secret with CIMD
CIMD_ALLOWED_AUTH_METHODS = {"none", "private_key_jwt"}


@dataclass
class CIMDCacheEntry:
    """Cache entry for CIMD metadata."""

    metadata: dict[str, Any]
    fetched_at: float
    expires_at: float
    etag: str | None = None


class CIMDError(Exception):
    """Base exception for CIMD-related errors."""

    pass


class CIMDFetchError(CIMDError):
    """Error fetching CIMD metadata document."""

    pass


class CIMDValidationError(CIMDError):
    """Error validating CIMD metadata document."""

    pass


class CIMDFetcher:
    """
    Fetches and validates Client ID Metadata Documents.

    This class handles:
    - Detecting URL-based client_ids
    - Fetching metadata from HTTPS URLs
    - Validating metadata structure and required fields
    - Caching metadata to reduce network requests
    """

    def __init__(
        self,
        cache_ttl_seconds: int = CIMD_CACHE_TTL_SECONDS,
        max_document_size: int = CIMD_MAX_DOCUMENT_SIZE,
        allow_localhost: bool = True,
    ):
        """
        Initialize the CIMD fetcher.

        Args:
            cache_ttl_seconds: How long to cache metadata documents
            max_document_size: Maximum allowed document size in bytes
            allow_localhost: Whether to allow localhost URLs (for development)
        """
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_document_size = max_document_size
        self.allow_localhost = allow_localhost
        self._cache: dict[str, CIMDCacheEntry] = {}
        self._cache_lock = asyncio.Lock()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for metadata fetches."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=CIMD_FETCH_TIMEOUT_SECONDS,
                connect=CIMD_CONNECT_TIMEOUT_SECONDS,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "MCP-Auth-Server/1.0 (CIMD)",
                },
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def is_cimd_client_id(self, client_id: str) -> bool:
        """
        Check if a client_id is a CIMD URL.

        A CIMD client_id is a URL starting with https:// (or http://localhost for dev).

        Args:
            client_id: The client_id to check

        Returns:
            True if this is a CIMD URL, False otherwise
        """
        if not client_id:
            return False

        try:
            parsed = urlparse(client_id)

            # Must have a scheme
            if not parsed.scheme:
                return False

            # HTTPS is required for production
            if parsed.scheme == "https":
                return True

            # Allow localhost HTTP for development
            if self.allow_localhost and parsed.scheme == "http":
                hostname = parsed.hostname or ""
                if hostname in ("localhost", "127.0.0.1", "::1"):
                    return True

            return False

        except Exception:
            return False

    def _validate_url(self, url: str) -> None:
        """
        Validate that a URL is acceptable for CIMD.

        Args:
            url: The URL to validate

        Raises:
            CIMDValidationError: If the URL is not valid for CIMD
        """
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise CIMDValidationError(f"Invalid URL format: {e}") from e

        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            raise CIMDValidationError("URL must have scheme and host")

        # HTTPS required for production
        if parsed.scheme == "https":
            return

        # Allow localhost HTTP for development
        if self.allow_localhost and parsed.scheme == "http":
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "::1"):
                return

        raise CIMDValidationError(
            f"CIMD URLs must use HTTPS (got {parsed.scheme}://{parsed.netloc})"
        )

    def _validate_metadata(self, url: str, metadata: dict[str, Any]) -> None:
        """
        Validate CIMD metadata document structure and required fields.

        Args:
            url: The URL the metadata was fetched from
            metadata: The parsed metadata document

        Raises:
            CIMDValidationError: If the metadata is invalid
        """
        # client_id must match the URL (simple string comparison per RFC 3986 6.2.1)
        client_id = metadata.get("client_id")
        if not client_id:
            raise CIMDValidationError("Missing required field: client_id")

        if client_id != url:
            raise CIMDValidationError(
                f"client_id mismatch: document contains '{client_id}' but was fetched from '{url}'"
            )

        # redirect_uris is required
        redirect_uris = metadata.get("redirect_uris")
        if redirect_uris is None:
            raise CIMDValidationError("Missing required field: redirect_uris")
        if not isinstance(redirect_uris, list) or len(redirect_uris) == 0:
            raise CIMDValidationError("redirect_uris must be a non-empty array")

        # Validate redirect URIs
        for uri in redirect_uris:
            if not isinstance(uri, str):
                raise CIMDValidationError("redirect_uris must contain strings")
            # Basic validation - must be a valid URI
            try:
                parsed = urlparse(uri)
                if not parsed.scheme or not parsed.netloc:
                    raise CIMDValidationError(f"Invalid redirect_uri: {uri}")
            except Exception as e:
                raise CIMDValidationError(f"Invalid redirect_uri '{uri}': {e}") from e

        # Validate token_endpoint_auth_method if present
        auth_method = metadata.get("token_endpoint_auth_method", "none")
        if auth_method not in CIMD_ALLOWED_AUTH_METHODS:
            raise CIMDValidationError(
                f"Invalid token_endpoint_auth_method: {auth_method}. "
                f"CIMD clients must use one of: {CIMD_ALLOWED_AUTH_METHODS}"
            )

        # If using private_key_jwt, must have jwks or jwks_uri
        if auth_method == "private_key_jwt" and not metadata.get("jwks") and not metadata.get("jwks_uri"):
            raise CIMDValidationError(
                "Clients using private_key_jwt must provide jwks or jwks_uri"
            )

        # client_name is recommended but not required
        if "client_name" in metadata and not isinstance(metadata["client_name"], str):
            raise CIMDValidationError("client_name must be a string")

    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key for a URL."""
        return hashlib.sha256(url.encode()).hexdigest()

    async def _get_cached(self, url: str) -> dict[str, Any] | None:
        """
        Get cached metadata if available and not expired.

        Args:
            url: The CIMD URL

        Returns:
            Cached metadata dict or None if not cached/expired
        """
        cache_key = self._get_cache_key(url)

        async with self._cache_lock:
            entry = self._cache.get(cache_key)
            if not entry:
                return None

            # Check if expired
            if time.time() > entry.expires_at:
                del self._cache[cache_key]
                return None

            return entry.metadata

    async def _set_cached(
        self, url: str, metadata: dict[str, Any], etag: str | None = None
    ) -> None:
        """
        Cache metadata for a URL.

        Args:
            url: The CIMD URL
            metadata: The metadata to cache
            etag: Optional ETag from the response
        """
        cache_key = self._get_cache_key(url)
        now = time.time()

        async with self._cache_lock:
            self._cache[cache_key] = CIMDCacheEntry(
                metadata=metadata,
                fetched_at=now,
                expires_at=now + self.cache_ttl_seconds,
                etag=etag,
            )

    async def fetch_metadata(self, url: str, use_cache: bool = True) -> dict[str, Any]:
        """
        Fetch and validate CIMD metadata from a URL.

        Args:
            url: The CIMD URL to fetch
            use_cache: Whether to use cached metadata

        Returns:
            Validated metadata dictionary

        Raises:
            CIMDFetchError: If the metadata cannot be fetched
            CIMDValidationError: If the metadata is invalid
        """
        # Validate URL
        self._validate_url(url)

        # Check cache
        if use_cache:
            cached = await self._get_cached(url)
            if cached:
                logger.debug(f"Using cached CIMD metadata for {url}")
                return cached

        # Fetch metadata
        logger.info(f"Fetching CIMD metadata from {url}")
        session = await self._get_session()

        try:
            async with session.get(url) as response:
                # Check status
                if response.status != 200:
                    raise CIMDFetchError(
                        f"Failed to fetch CIMD metadata: HTTP {response.status}"
                    )

                # Check content type
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("application/json"):
                    logger.warning(
                        f"CIMD metadata has unexpected Content-Type: {content_type}"
                    )

                # Check content length
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > self.max_document_size:
                    raise CIMDFetchError(
                        f"CIMD metadata exceeds maximum size: {content_length} > {self.max_document_size}"
                    )

                # Read and parse JSON
                body = await response.read()
                if len(body) > self.max_document_size:
                    raise CIMDFetchError(
                        f"CIMD metadata exceeds maximum size: {len(body)} > {self.max_document_size}"
                    )

                try:
                    metadata = await response.json()
                except Exception as e:
                    raise CIMDFetchError(f"Invalid JSON in CIMD metadata: {e}") from e

                if not isinstance(metadata, dict):
                    raise CIMDFetchError("CIMD metadata must be a JSON object")

                # Validate metadata
                self._validate_metadata(url, metadata)

                # Cache the result
                etag = response.headers.get("ETag")
                await self._set_cached(url, metadata, etag)

                logger.info(f"Successfully fetched CIMD metadata for {url}")
                return metadata

        except aiohttp.ClientError as e:
            raise CIMDFetchError(f"Network error fetching CIMD metadata: {e}") from e
        except TimeoutError as e:
            raise CIMDFetchError("Timeout fetching CIMD metadata") from e

    async def get_client_info(self, client_id: str) -> OAuthClientInformationFull | None:
        """
        Get OAuth client information from a CIMD URL.

        This fetches the metadata document and converts it to OAuthClientInformationFull.

        Args:
            client_id: The CIMD URL (client_id)

        Returns:
            OAuthClientInformationFull if valid, None if not a CIMD URL

        Raises:
            CIMDError: If fetching or validation fails
        """
        if not self.is_cimd_client_id(client_id):
            return None

        metadata = await self.fetch_metadata(client_id)

        # Convert to OAuthClientInformationFull
        # Note: CIMD clients cannot have client_secret (no shared secrets)
        auth_method = metadata.get("token_endpoint_auth_method", "none")

        # Extract grant types (default to authorization_code + refresh_token)
        grant_types = metadata.get(
            "grant_types", ["authorization_code", "refresh_token"]
        )

        # Extract response types (default to code)
        response_types = metadata.get("response_types", ["code"])

        # Extract scope (as space-separated string)
        scope = metadata.get("scope")
        if isinstance(scope, list):
            scope = " ".join(scope)

        return OAuthClientInformationFull(
            client_id=metadata["client_id"],
            client_secret=None,  # CIMD clients never have shared secrets
            redirect_uris=metadata["redirect_uris"],
            grant_types=grant_types,
            response_types=response_types,
            token_endpoint_auth_method=auth_method,
            scope=scope,
            # Store additional CIMD-specific fields for later use
            # These are accessed via the metadata cache
        )

    async def get_jwks(self, client_id: str) -> dict[str, Any] | None:
        """
        Get the JWKS for a CIMD client using private_key_jwt.

        Args:
            client_id: The CIMD URL

        Returns:
            JWKS dictionary or None if not available
        """
        if not self.is_cimd_client_id(client_id):
            return None

        metadata = await self.fetch_metadata(client_id)

        # Check for inline JWKS
        if "jwks" in metadata:
            return metadata["jwks"]

        # Check for jwks_uri
        jwks_uri = metadata.get("jwks_uri")
        if jwks_uri:
            # Fetch JWKS from URI
            session = await self._get_session()
            try:
                async with session.get(jwks_uri) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch JWKS from {jwks_uri}: HTTP {response.status}")
                        return None
                    return await response.json()
            except Exception as e:
                logger.error(f"Error fetching JWKS from {jwks_uri}: {e}")
                return None

        return None

    def clear_cache(self) -> None:
        """Clear all cached metadata."""
        self._cache.clear()

    async def invalidate_cache(self, url: str) -> None:
        """
        Invalidate cached metadata for a specific URL.

        Args:
            url: The CIMD URL to invalidate
        """
        cache_key = self._get_cache_key(url)
        async with self._cache_lock:
            self._cache.pop(cache_key, None)


# Global CIMD fetcher instance
_cimd_fetcher: CIMDFetcher | None = None


def get_cimd_fetcher() -> CIMDFetcher:
    """Get the global CIMD fetcher instance."""
    global _cimd_fetcher
    if _cimd_fetcher is None:
        _cimd_fetcher = CIMDFetcher()
    return _cimd_fetcher


async def cleanup_cimd_fetcher() -> None:
    """Clean up the global CIMD fetcher instance."""
    global _cimd_fetcher
    if _cimd_fetcher:
        await _cimd_fetcher.close()
        _cimd_fetcher = None
