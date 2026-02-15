"""Tests for SSRF protection in RSS feed fetching."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.feed_source import FeedSource, FeedType
from app.models.user import User
from app.services.news_fetcher import (
    _is_ip_blocked,
    _safe_fetch_feed_content,
    validate_feed_url,
)

# =============================================================================
# Unit tests for validate_feed_url
# =============================================================================


class TestValidateFeedUrl:
    def test_rejects_file_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_feed_url("file:///etc/passwd")

    def test_rejects_ftp_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_feed_url("ftp://example.com/feed.xml")

    def test_rejects_gopher_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_feed_url("gopher://example.com/feed")

    def test_rejects_javascript_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_feed_url("javascript:alert(1)")

    def test_rejects_no_hostname(self):
        with pytest.raises(ValueError, match="no hostname"):
            validate_feed_url("http://")

    def test_accepts_http(self):
        validate_feed_url("http://example.com/feed.xml")

    def test_accepts_https(self):
        validate_feed_url("https://example.com/feed.xml")


# =============================================================================
# Unit tests for _is_ip_blocked
# =============================================================================


class TestIsIpBlocked:
    # IPv4 blocked addresses
    def test_blocks_localhost(self):
        assert _is_ip_blocked("127.0.0.1") is True

    def test_blocks_localhost_variant(self):
        assert _is_ip_blocked("127.0.0.2") is True

    def test_blocks_10_network(self):
        assert _is_ip_blocked("10.0.0.1") is True
        assert _is_ip_blocked("10.255.255.255") is True

    def test_blocks_172_16_network(self):
        assert _is_ip_blocked("172.16.0.1") is True
        assert _is_ip_blocked("172.31.255.255") is True

    def test_blocks_192_168_network(self):
        assert _is_ip_blocked("192.168.0.1") is True
        assert _is_ip_blocked("192.168.255.255") is True

    def test_blocks_link_local(self):
        assert _is_ip_blocked("169.254.0.1") is True
        assert _is_ip_blocked("169.254.169.254") is True  # AWS metadata

    # IPv6 blocked addresses
    def test_blocks_ipv6_localhost(self):
        assert _is_ip_blocked("::1") is True

    def test_blocks_ipv6_unique_local(self):
        assert _is_ip_blocked("fc00::1") is True
        assert _is_ip_blocked("fd12:3456::1") is True

    def test_blocks_ipv6_link_local(self):
        assert _is_ip_blocked("fe80::1") is True

    # Allowed addresses
    def test_allows_public_ip(self):
        assert _is_ip_blocked("8.8.8.8") is False
        assert _is_ip_blocked("1.1.1.1") is False

    def test_allows_public_ipv6(self):
        assert _is_ip_blocked("2001:4860:4860::8888") is False

    def test_blocks_unparseable_ip(self):
        assert _is_ip_blocked("not-an-ip") is True


# =============================================================================
# Unit tests for _safe_fetch_feed_content
# =============================================================================


class TestSafeFetchFeedContent:
    @pytest.mark.asyncio
    async def test_rejects_invalid_scheme(self):
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            await _safe_fetch_feed_content("file:///etc/passwd")

    @pytest.mark.asyncio
    async def test_timeout_on_slow_server(self):
        """Verify that feed fetching has a timeout."""
        with patch("app.services.news_fetcher.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = httpx.ReadTimeout("Read timed out")
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.ReadTimeout):
                await _safe_fetch_feed_content("https://slow-server.com/feed")

    @pytest.mark.asyncio
    async def test_fetches_content_successfully(self):
        """Verify successful content fetch returns response text."""
        mock_response = MagicMock()
        mock_response.text = "<rss>test feed</rss>"
        mock_response.extensions = {}
        mock_response.raise_for_status = MagicMock()

        with patch("app.services.news_fetcher.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = await _safe_fetch_feed_content("https://example.com/feed.xml")
            assert result == "<rss>test feed</rss>"


# =============================================================================
# API integration tests for SSRF protection
# =============================================================================

ADMIN_PASSWORD = "AdminPass123!"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def admin_user_ssrf(db_session: AsyncSession) -> User:
    """Create an admin test user for SSRF tests."""
    user = User(
        email="ssrf-admin@example.com",
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_client_ssrf(client: AsyncClient, admin_user_ssrf: User) -> AsyncClient:
    """Create an authenticated admin client for SSRF tests."""
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "ssrf-admin@example.com",
            "password": ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200
    return client


class TestCreateFeedSourceSsrf:
    @pytest.mark.asyncio
    async def test_rejects_file_scheme(self, admin_client_ssrf: AsyncClient):
        response = await admin_client_ssrf.post(
            "/api/news/sources",
            json={
                "name": "Evil Feed",
                "url": "file:///etc/passwd",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_ftp_scheme(self, admin_client_ssrf: AsyncClient):
        response = await admin_client_ssrf.post(
            "/api/news/sources",
            json={
                "name": "FTP Feed",
                "url": "ftp://internal/feed.xml",
            },
        )
        assert response.status_code == 400


class TestUpdateFeedSourceSsrf:
    @pytest.mark.asyncio
    async def test_rejects_internal_url_on_update(
        self,
        admin_client_ssrf: AsyncClient,
        db_session: AsyncSession,
    ):
        """Updating a feed source URL must also validate for SSRF."""
        source = FeedSource(
            name="Safe Feed",
            url="https://example.com/feed.xml",
            type=FeedType.article,
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)

        response = await admin_client_ssrf.put(
            f"/api/news/sources/{source.id}",
            json={"url": "file:///etc/passwd"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_allows_valid_url_on_update(
        self,
        admin_client_ssrf: AsyncClient,
        db_session: AsyncSession,
    ):
        """Updating to a valid URL should succeed."""
        source = FeedSource(
            name="Update Test Feed",
            url="https://example.com/feed.xml",
            type=FeedType.article,
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)

        response = await admin_client_ssrf.put(
            f"/api/news/sources/{source.id}",
            json={"url": "https://new-safe-url.com/feed.xml"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["url"] == "https://new-safe-url.com/feed.xml"

    @pytest.mark.asyncio
    async def test_non_url_update_skips_validation(
        self,
        admin_client_ssrf: AsyncClient,
        db_session: AsyncSession,
    ):
        """Updating non-URL fields should not trigger URL validation."""
        source = FeedSource(
            name="No URL Change Feed",
            url="https://example.com/feed.xml",
            type=FeedType.article,
            is_active=True,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)

        response = await admin_client_ssrf.put(
            f"/api/news/sources/{source.id}",
            json={"name": "Renamed Feed"},
        )
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Renamed Feed"
