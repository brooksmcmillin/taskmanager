"""Tests for authentication dependency functions."""

import json
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import generate_token, hash_password
from app.dependencies import (
    get_admin_user,
    get_current_user,
    get_current_user_flexible,
    get_current_user_oauth,
    get_optional_user,
    validate_client_credentials_token,
)
from app.models.oauth import AccessToken, OAuthClient
from app.models.session import Session
from app.models.user import User


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("TestPass123!"),  # pragma: allowlist secret
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="admin@example.com",
        password_hash=hash_password("AdminPass123!"),  # pragma: allowlist secret
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create a test session."""
    session = Session(
        id=generate_token(),
        user_id=test_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def expired_session(db_session: AsyncSession, test_user: User) -> Session:
    """Create an expired test session."""
    session = Session(
        id=generate_token(),
        user_id=test_user.id,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def oauth_client(db_session: AsyncSession) -> OAuthClient:
    """Create a test OAuth client."""
    client = OAuthClient(
        client_id="test-client-id",
        client_secret_hash=hash_password("test-secret"),  # pragma: allowlist secret
        name="Test Client",
        redirect_uris=json.dumps(["http://localhost:3000/callback"]),
        grant_types=json.dumps(["authorization_code", "client_credentials"]),
        scopes=json.dumps(["read", "write"]),
        is_public=False,
        is_active=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def user_access_token(
    db_session: AsyncSession, test_user: User, oauth_client: OAuthClient
) -> AccessToken:
    """Create a test user access token."""
    token = AccessToken(
        token=generate_token(),
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read", "write"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def client_credentials_token(
    db_session: AsyncSession, oauth_client: OAuthClient
) -> AccessToken:
    """Create a test client credentials access token (no user)."""
    token = AccessToken(
        token=generate_token(),
        client_id=oauth_client.client_id,
        user_id=None,  # Client credentials tokens have no user
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


@pytest_asyncio.fixture
async def expired_access_token(
    db_session: AsyncSession, test_user: User, oauth_client: OAuthClient
) -> AccessToken:
    """Create an expired access token."""
    token = AccessToken(
        token=generate_token(),
        client_id=oauth_client.client_id,
        user_id=test_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    return token


# =============================================================================
# Session-based Authentication Tests (get_current_user)
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_success(
    db_session: AsyncSession, test_user: User, test_session: Session
):
    """Test successful user authentication via session cookie."""
    # Create mock request with session cookie
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": test_session.id}

    user = await get_current_user(request, db_session)

    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_current_user_missing_cookie(db_session: AsyncSession):
    """Test authentication fails when session cookie is missing."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {}

    with pytest.raises(ApiError) as exc_info:
        await get_current_user(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_002" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_invalid_session(
    db_session: AsyncSession, test_user: User
):
    """Test authentication fails with invalid session ID."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": "invalid-session-id"}

    with pytest.raises(ApiError) as exc_info:
        await get_current_user(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_003" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_expired_session(
    db_session: AsyncSession, test_user: User, expired_session: Session
):
    """Test authentication fails with expired session."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": expired_session.id}

    with pytest.raises(ApiError) as exc_info:
        await get_current_user(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_003" in str(exc_info.value.detail)


# =============================================================================
# OAuth Bearer Token Authentication Tests (get_current_user_oauth)
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_oauth_success(
    db_session: AsyncSession, test_user: User, user_access_token: AccessToken
):
    """Test successful OAuth authentication with Bearer token."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {user_access_token.token}".encode())
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    user = await get_current_user_oauth(request, db_session)

    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_current_user_oauth_missing_header(db_session: AsyncSession):
    """Test OAuth authentication fails when Authorization header is missing."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_oauth(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_002" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_oauth_invalid_format(db_session: AsyncSession):
    """Test OAuth authentication fails with invalid Authorization header format."""
    # Test without "Bearer " prefix
    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", b"InvalidToken")],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_oauth(request, db_session)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_oauth_invalid_token(db_session: AsyncSession):
    """Test OAuth authentication fails with invalid token."""
    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", b"Bearer invalid-token")],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_oauth(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_004" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_oauth_expired_token(
    db_session: AsyncSession, test_user: User, expired_access_token: AccessToken
):
    """Test OAuth authentication fails with expired token."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {expired_access_token.token}".encode())
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_oauth(request, db_session)

    assert exc_info.value.status_code == 401
    assert "AUTH_004" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_current_user_oauth_client_credentials_token(
    db_session: AsyncSession, client_credentials_token: AccessToken
):
    """Test OAuth authentication fails when using client credentials token (no user)."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {client_credentials_token.token}".encode())
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_oauth(request, db_session)

    assert exc_info.value.status_code == 401


# =============================================================================
# Client Credentials Token Validation Tests
# =============================================================================


@pytest.mark.asyncio
async def test_validate_client_credentials_token_success(
    db_session: AsyncSession,
    oauth_client: OAuthClient,
    client_credentials_token: AccessToken,
):
    """Test successful client credentials token validation."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (
                    b"authorization",
                    f"Bearer {client_credentials_token.token}".encode(),
                )
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    client_id = await validate_client_credentials_token(request, db_session)

    assert client_id == oauth_client.client_id


@pytest.mark.asyncio
async def test_validate_client_credentials_token_with_regular_user_id(
    db_session: AsyncSession, test_user: User, user_access_token: AccessToken
):
    """Test client credentials validation fails when token belongs to a regular user."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {user_access_token.token}".encode())
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await validate_client_credentials_token(request, db_session)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_validate_client_credentials_token_with_service_account(
    db_session: AsyncSession, oauth_client: OAuthClient
):
    """Test client credentials validation succeeds for service account tokens."""
    # Create a service account user
    service_user = User(
        email="svc@service.local",
        password_hash="!unusable_service_account_password",
        is_service_account=True,
    )
    db_session.add(service_user)
    await db_session.flush()

    # Create a token linked to the service account
    token = AccessToken(
        token=generate_token(),
        client_id=oauth_client.client_id,
        user_id=service_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.commit()

    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token.token}".encode())],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    client_id = await validate_client_credentials_token(request, db_session)
    assert client_id == oauth_client.client_id


@pytest.mark.asyncio
async def test_validate_client_credentials_token_with_inactive_service_account(
    db_session: AsyncSession, oauth_client: OAuthClient
):
    """Test client credentials validation fails for inactive service account."""
    service_user = User(
        email="inactive-svc@service.local",
        password_hash="!unusable_service_account_password",
        is_service_account=True,
        is_active=False,
    )
    db_session.add(service_user)
    await db_session.flush()

    token = AccessToken(
        token=generate_token(),
        client_id=oauth_client.client_id,
        user_id=service_user.id,
        scopes=json.dumps(["read"]),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(token)
    await db_session.commit()

    request = Request(
        scope={
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token.token}".encode())],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )

    with pytest.raises(ApiError) as exc_info:
        await validate_client_credentials_token(request, db_session)

    assert exc_info.value.status_code == 401


# =============================================================================
# Flexible Authentication Tests (get_current_user_flexible)
# =============================================================================


@pytest.mark.asyncio
async def test_get_current_user_flexible_oauth(
    db_session: AsyncSession, test_user: User, user_access_token: AccessToken
):
    """Test flexible auth uses OAuth when Bearer token is present."""
    request = Request(
        scope={
            "type": "http",
            "headers": [
                (b"authorization", f"Bearer {user_access_token.token}".encode())
            ],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {}

    user = await get_current_user_flexible(request, db_session)

    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_current_user_flexible_session(
    db_session: AsyncSession, test_user: User, test_session: Session
):
    """Test flexible auth falls back to session when no Bearer token."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": test_session.id}

    user = await get_current_user_flexible(request, db_session)

    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_current_user_flexible_no_auth(db_session: AsyncSession):
    """Test flexible auth fails when no authentication is provided."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {}

    with pytest.raises(ApiError) as exc_info:
        await get_current_user_flexible(request, db_session)

    assert exc_info.value.status_code == 401


# =============================================================================
# Admin User Tests (get_admin_user)
# =============================================================================


@pytest.mark.asyncio
async def test_get_admin_user_success(db_session: AsyncSession, admin_user: User):
    """Test successful admin user authentication."""
    # Create session for admin user
    admin_session = Session(
        id=generate_token(),
        user_id=admin_user.id,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db_session.add(admin_session)
    await db_session.commit()

    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": admin_session.id}

    user = await get_admin_user(request, db_session)

    assert user.id == admin_user.id
    assert user.is_admin is True


@pytest.mark.asyncio
async def test_get_admin_user_non_admin(
    db_session: AsyncSession, test_user: User, test_session: Session
):
    """Test admin authentication fails for non-admin user."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": test_session.id}

    with pytest.raises(ApiError) as exc_info:
        await get_admin_user(request, db_session)

    assert exc_info.value.status_code == 403
    assert "AUTHZ_001" in str(exc_info.value.detail)


# =============================================================================
# Optional User Tests (get_optional_user)
# =============================================================================


@pytest.mark.asyncio
async def test_get_optional_user_authenticated(
    db_session: AsyncSession, test_user: User, test_session: Session
):
    """Test optional user returns user when authenticated."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {"session": test_session.id}

    user = await get_optional_user(request, db_session)

    assert user is not None
    assert user.id == test_user.id


@pytest.mark.asyncio
async def test_get_optional_user_not_authenticated(db_session: AsyncSession):
    """Test optional user returns None when not authenticated."""
    request = Request(
        scope={
            "type": "http",
            "headers": [],
            "query_string": b"",
            "root_path": "",
            "path": "/",
            "method": "GET",
            "scheme": "http",
        }
    )
    request._cookies = {}

    user = await get_optional_user(request, db_session)

    assert user is None
