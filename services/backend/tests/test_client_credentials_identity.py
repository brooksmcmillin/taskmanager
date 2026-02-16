"""Tests for Phase 2: Client Credentials with Identity.

Verifies that tokens issued via the client credentials grant carry the
service account's user_id, enabling action attribution through existing
get_current_user_oauth() paths.
"""

import json

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_token, hash_password
from app.models.oauth import OAuthClient
from app.models.user import User

ADMIN_PASSWORD = "AdminPass123!"  # pragma: allowlist secret
SA_BASE_URL = "/api/admin/service-accounts"
TOKEN_URL = "/api/oauth/token"
VERIFY_URL = "/api/oauth/verify"


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="cc-admin@example.com",
        password_hash=hash_password(ADMIN_PASSWORD),
        is_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: User) -> AsyncClient:
    """Create an authenticated admin client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "cc-admin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def service_account_credentials(
    admin_client: AsyncClient,
) -> dict:
    """Create a service account and return its credentials.

    Returns dict with keys: client_id, client_secret, account_id.
    """
    response = await admin_client.post(
        SA_BASE_URL,
        json={
            "display_name": "Test Bot",
            "email": "test-bot@agents.taskmanager.local",
            "scopes": ["read", "write"],
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    return {
        "client_id": data["client_id"],
        "client_secret": data["client_secret"],
        "account_id": data["service_account"]["id"],
    }


@pytest_asyncio.fixture
async def system_client(db_session: AsyncSession) -> dict:
    """Create a system OAuth client with no linked user (backward compat).

    Returns dict with keys: client_id, client_secret.
    """
    client_id = generate_token(16)
    raw_secret = generate_token(32)
    client_secret_hash = hash_password(raw_secret)

    oauth_client = OAuthClient(
        user_id=None,
        client_id=client_id,
        client_secret_hash=client_secret_hash,
        name="system-test-client",
        redirect_uris=json.dumps([]),
        grant_types=json.dumps(["client_credentials"]),
        scopes=json.dumps(["read"]),
        is_public=False,
    )
    db_session.add(oauth_client)
    await db_session.commit()
    return {"client_id": client_id, "client_secret": raw_secret}


# ---------------------------------------------------------------------------
# 2.1 — Client credentials token carries service account user_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_credentials_token_has_user_id(
    client: AsyncClient,
    service_account_credentials: dict,
) -> None:
    """A client credentials token for a service account should carry user_id."""
    creds = service_account_credentials

    # Get token
    response = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    # Verify token carries user_id
    verify_resp = await client.get(
        VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["valid"] is True
    assert verify_data["user_id"] == creds["account_id"]
    assert verify_data["client_id"] == creds["client_id"]


# ---------------------------------------------------------------------------
# 2.2 — Backward compatibility: system client tokens have user_id=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_client_token_has_no_user_id(
    client: AsyncClient,
    system_client: dict,
) -> None:
    """Tokens for system clients without a linked user keep user_id=None."""
    response = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": system_client["client_id"],
            "client_secret": system_client["client_secret"],
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    verify_resp = await client.get(
        VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["user_id"] is None


# ---------------------------------------------------------------------------
# 2.3 — Service account token can create a task attributed to the bot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_account_token_creates_attributed_task(
    client: AsyncClient,
    service_account_credentials: dict,
    db_session: AsyncSession,
) -> None:
    """Using a service account token to create a task should attribute it
    to the service account user."""
    creds = service_account_credentials

    # Get token
    tok_resp = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    assert tok_resp.status_code == 200
    token = tok_resp.json()["access_token"]

    # Create a task using the service account token
    task_resp = await client.post(
        "/api/todos",
        json={"title": "Task by bot"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert task_resp.status_code == 201
    task_data = task_resp.json()["data"]
    todo_id = task_data["id"]

    # Verify the task is attributed to the service account in the database
    from app.models.todo import Todo

    result = await db_session.execute(select(Todo).where(Todo.id == todo_id))
    todo = result.scalar_one()
    assert todo.user_id == creds["account_id"]


# ---------------------------------------------------------------------------
# 2.4 — Inactive service account cannot get tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inactive_service_account_rejected(
    client: AsyncClient,
    admin_client: AsyncClient,
    service_account_credentials: dict,
) -> None:
    """Deactivating a service account should prevent new token issuance."""
    creds = service_account_credentials

    # Deactivate the service account
    deactivate_resp = await admin_client.delete(
        f"{SA_BASE_URL}/{creds['account_id']}"
    )
    assert deactivate_resp.status_code == 200

    # Attempt to get a token — should fail
    response = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    # OAuthClient is also deactivated, so client lookup fails
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2.5 — Non-service-account user linked to client is rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_service_account_user_linked_to_client_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A client linked to a regular user (not a service account) should
    be rejected during client credentials grant."""
    # Create a regular user
    regular_user = User(
        email="regular-linked@example.com",
        password_hash=hash_password("SomePass123!"),
        is_service_account=False,
    )
    db_session.add(regular_user)
    await db_session.flush()

    # Create an OAuth client linked to that regular user
    raw_secret = generate_token(32)
    oauth_client = OAuthClient(
        user_id=regular_user.id,
        client_id=generate_token(16),
        client_secret_hash=hash_password(raw_secret),
        name="bad-link-client",
        redirect_uris=json.dumps([]),
        grant_types=json.dumps(["client_credentials"]),
        scopes=json.dumps(["read"]),
        is_public=False,
    )
    db_session.add(oauth_client)
    await db_session.commit()

    # Attempt to get a token — should fail because user is not a service account
    response = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": oauth_client.client_id,
            "client_secret": raw_secret,
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2.6 — Verify endpoint returns user_id for service account tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_returns_user_id_for_service_account(
    client: AsyncClient,
    service_account_credentials: dict,
) -> None:
    """The /api/oauth/verify endpoint should include user_id in the
    response for service account tokens."""
    creds = service_account_credentials

    tok_resp = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    token = tok_resp.json()["access_token"]

    verify_resp = await client.get(
        VERIFY_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["valid"] is True
    assert data["user_id"] == creds["account_id"]
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] > 0


# ---------------------------------------------------------------------------
# 2.7 — Scope passthrough: requested scopes appear on the token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_account_token_scopes(
    client: AsyncClient,
    service_account_credentials: dict,
) -> None:
    """Service account tokens should carry the requested scopes."""
    creds = service_account_credentials

    tok_resp = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "scope": "read",
        },
    )
    assert tok_resp.status_code == 200
    assert tok_resp.json()["scope"] == "read"

    # Default scopes (no scope param)
    tok_resp2 = await client.post(
        TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        },
    )
    assert tok_resp2.status_code == 200
    assert "read" in tok_resp2.json()["scope"]
    assert "write" in tok_resp2.json()["scope"]
