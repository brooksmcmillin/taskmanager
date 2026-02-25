"""Tests for service account management endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User

ADMIN_PASSWORD = "AdminPass123!"  # pragma: allowlist secret
USER_PASSWORD = "UserPass123!"  # pragma: allowlist secret

BASE_URL = "/api/admin/service-accounts"


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin test user."""
    user = User(
        email="sa-admin@example.com",
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
        json={"email": "sa-admin@example.com", "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    return client


@pytest_asyncio.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create a non-admin test user."""
    user = User(
        email="sa-user@example.com",
        password_hash=hash_password(USER_PASSWORD),
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_client(client: AsyncClient, regular_user: User) -> AsyncClient:
    """Create an authenticated non-admin client."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "sa-user@example.com", "password": USER_PASSWORD},
    )
    assert response.status_code == 200
    return client


# ---------------------------------------------------------------------------
# Authorization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    """Unauthenticated requests to service account endpoints should get 401."""
    response = await client.get(BASE_URL)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_returns_403(regular_client: AsyncClient) -> None:
    """Non-admin users should get 403 on service account endpoints."""
    response = await regular_client.get(BASE_URL)
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_service_account(admin_client: AsyncClient) -> None:
    """Admin can create a service account and receives credentials."""
    response = await admin_client.post(
        BASE_URL,
        json={
            "display_name": "CI Bot",
            "email": "ci-bot@agents.taskmanager.local",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]

    # Credentials are returned
    assert "client_id" in data
    assert "client_secret" in data
    assert len(data["client_id"]) > 0
    assert len(data["client_secret"]) > 0

    # Service account fields
    sa = data["service_account"]
    assert sa["email"] == "ci-bot@agents.taskmanager.local"
    assert sa["display_name"] == "CI Bot"
    assert sa["is_service_account"] is True
    assert sa["is_active"] is True
    assert sa["oauth_client_id"] == data["client_id"]
    assert sa["scopes"] == ["read"]  # default scope


@pytest.mark.asyncio
async def test_create_service_account_custom_scopes(
    admin_client: AsyncClient,
) -> None:
    """Service accounts can be created with custom scopes."""
    response = await admin_client.post(
        BASE_URL,
        json={
            "display_name": "Deploy Bot",
            "email": "deploy@agents.taskmanager.local",
            "scopes": ["read", "write"],
        },
    )

    assert response.status_code == 201
    sa = response.json()["data"]["service_account"]
    assert sa["scopes"] == ["read", "write"]


@pytest.mark.asyncio
async def test_create_service_account_duplicate_email(
    admin_client: AsyncClient,
) -> None:
    """Creating a service account with a duplicate email returns 409."""
    payload = {
        "display_name": "Bot 1",
        "email": "dup-bot@agents.taskmanager.local",
    }

    response1 = await admin_client.post(BASE_URL, json=payload)
    assert response1.status_code == 201

    response2 = await admin_client.post(BASE_URL, json=payload)
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_create_service_account_validation(admin_client: AsyncClient) -> None:
    """Missing required fields return 422."""
    # Missing email
    response = await admin_client.post(
        BASE_URL,
        json={"display_name": "No Email Bot"},
    )
    assert response.status_code == 422

    # Missing display_name
    response = await admin_client.post(
        BASE_URL,
        json={"email": "no-name@agents.local"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_service_accounts_empty(admin_client: AsyncClient) -> None:
    """Listing service accounts when none exist returns empty list."""
    response = await admin_client.get(BASE_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["data"] == []
    assert data["meta"]["count"] == 0


@pytest.mark.asyncio
async def test_list_service_accounts(admin_client: AsyncClient) -> None:
    """Listing service accounts returns all created accounts."""
    # Create two service accounts
    await admin_client.post(
        BASE_URL,
        json={"display_name": "Bot A", "email": "bot-a@agents.local"},
    )
    await admin_client.post(
        BASE_URL,
        json={"display_name": "Bot B", "email": "bot-b@agents.local"},
    )

    response = await admin_client.get(BASE_URL)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["count"] == 2
    names = {sa["display_name"] for sa in data["data"]}
    assert names == {"Bot A", "Bot B"}


@pytest.mark.asyncio
async def test_list_excludes_regular_users(
    admin_client: AsyncClient,
    regular_user: User,
) -> None:
    """Listing service accounts does not include regular users."""
    response = await admin_client.get(BASE_URL)
    assert response.status_code == 200
    emails = {sa["email"] for sa in response.json()["data"]}
    assert regular_user.email not in emails


# ---------------------------------------------------------------------------
# Get by ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_service_account(admin_client: AsyncClient) -> None:
    """Admin can get a service account by ID."""
    create_resp = await admin_client.post(
        BASE_URL,
        json={"display_name": "Get Bot", "email": "get-bot@agents.local"},
    )
    account_id = create_resp.json()["data"]["service_account"]["id"]

    response = await admin_client.get(f"{BASE_URL}/{account_id}")
    assert response.status_code == 200
    assert response.json()["data"]["display_name"] == "Get Bot"


@pytest.mark.asyncio
async def test_get_nonexistent_service_account(admin_client: AsyncClient) -> None:
    """Getting a non-existent service account returns 404."""
    response = await admin_client.get(f"{BASE_URL}/99999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_regular_user_as_service_account(
    admin_client: AsyncClient,
    regular_user: User,
) -> None:
    """Getting a regular user by ID through the service account endpoint returns 404."""
    response = await admin_client.get(f"{BASE_URL}/{regular_user.id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_display_name(admin_client: AsyncClient) -> None:
    """Admin can update a service account's display name."""
    create_resp = await admin_client.post(
        BASE_URL,
        json={"display_name": "Old Name", "email": "rename@agents.local"},
    )
    account_id = create_resp.json()["data"]["service_account"]["id"]

    response = await admin_client.patch(
        f"{BASE_URL}/{account_id}",
        json={"display_name": "New Name"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_update_scopes(admin_client: AsyncClient) -> None:
    """Admin can update a service account's scopes."""
    create_resp = await admin_client.post(
        BASE_URL,
        json={"display_name": "Scope Bot", "email": "scope@agents.local"},
    )
    account_id = create_resp.json()["data"]["service_account"]["id"]

    response = await admin_client.patch(
        f"{BASE_URL}/{account_id}",
        json={"scopes": ["read", "write"]},
    )
    assert response.status_code == 200
    assert response.json()["data"]["scopes"] == ["read", "write"]


@pytest.mark.asyncio
async def test_update_deactivate(admin_client: AsyncClient) -> None:
    """Admin can deactivate a service account via PATCH."""
    create_resp = await admin_client.post(
        BASE_URL,
        json={"display_name": "Deact Bot", "email": "deact@agents.local"},
    )
    account_id = create_resp.json()["data"]["service_account"]["id"]

    response = await admin_client.patch(
        f"{BASE_URL}/{account_id}",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_update_nonexistent_returns_404(admin_client: AsyncClient) -> None:
    """Updating a non-existent service account returns 404."""
    response = await admin_client.patch(
        f"{BASE_URL}/99999",
        json={"display_name": "Ghost"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete (soft deactivate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_deactivates(admin_client: AsyncClient) -> None:
    """DELETE deactivates the service account and its OAuth client."""
    create_resp = await admin_client.post(
        BASE_URL,
        json={"display_name": "Del Bot", "email": "del@agents.local"},
    )
    account_id = create_resp.json()["data"]["service_account"]["id"]

    response = await admin_client.delete(f"{BASE_URL}/{account_id}")
    assert response.status_code == 200
    assert response.json()["data"]["deactivated"] is True

    # Verify the account is now inactive
    get_resp = await admin_client.get(f"{BASE_URL}/{account_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["is_active"] is False


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(admin_client: AsyncClient) -> None:
    """Deleting a non-existent service account returns 404."""
    response = await admin_client.delete(f"{BASE_URL}/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Service accounts cannot log in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_service_account_cannot_login(
    client: AsyncClient,
    admin_client: AsyncClient,
) -> None:
    """Service accounts should not be able to log in with a password."""
    # Create a service account
    await admin_client.post(
        BASE_URL,
        json={"display_name": "Login Bot", "email": "login-bot@agents.local"},
    )

    # Attempt to log in as the service account
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "login-bot@agents.local",
            "password": "anything",  # pragma: allowlist secret
        },
    )
    # Should fail — the password hash is locked
    assert response.status_code == 401
