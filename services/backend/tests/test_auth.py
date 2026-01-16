"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient

# Test passwords for authentication tests
TEST_PASSWORD = "SecurePass123!"  # pragma: allowlist secret
TEST_PASSWORD_WEAK = "weakpass"  # pragma: allowlist secret
TEST_PASSWORD_WRONG = "wrongpassword"  # pragma: allowlist secret
TEST_PASSWORD_LOGIN = "TestPass123!"  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful user registration."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Registration successful"
    assert data["user"]["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient, test_user):
    """Test registration with existing username."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "testuser",  # Already exists
            "email": "another@example.com",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONFLICT_001"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Test registration with weak password."""
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": TEST_PASSWORD_WEAK,  # No uppercase or special chars
        },
    )

    assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """Test successful login."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_PASSWORD_LOGIN},
    )

    assert response.status_code == 200
    assert "session" in response.cookies
    data = response.json()
    assert data["message"] == "Login successful"
    assert data["user"]["username"] == "testuser"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, test_user):
    """Test login with wrong password."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_001"


@pytest.mark.asyncio
async def test_logout(authenticated_client: AsyncClient):
    """Test logout."""
    response = await authenticated_client.post("/api/auth/logout")

    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"


@pytest.mark.asyncio
async def test_login_rate_limit_triggers(client: AsyncClient, test_user):
    """Test that rate limiting triggers after max failed attempts."""
    from app.core.rate_limit import login_rate_limiter

    # Ensure clean state for this test
    login_rate_limiter.reset("testuser")

    # Make 5 failed login attempts
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # 6th attempt should be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
    )

    assert response.status_code == 429
    data = response.json()
    assert data["detail"]["code"] == "RATE_001"
    assert "retry_after" in data["detail"]["details"]


@pytest.mark.asyncio
async def test_login_rate_limit_resets_on_success(client: AsyncClient, test_user):
    """Test that rate limiting resets after successful login."""
    # Make 3 failed attempts
    for _ in range(3):
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # Successful login should reset the counter
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_PASSWORD_LOGIN},
    )
    assert response.status_code == 200

    # Now we should be able to make failed attempts again without being rate limited
    for _ in range(3):
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_per_username(client: AsyncClient, test_user):
    """Test that rate limiting is per username, not global."""
    # Make 5 failed attempts for testuser
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # testuser should be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_PASSWORD_WRONG},
    )
    assert response.status_code == 429

    # But a different username should not be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"username": "otheruser", "password": TEST_PASSWORD_WRONG},
    )
    assert response.status_code == 401  # Invalid credentials, not rate limited
