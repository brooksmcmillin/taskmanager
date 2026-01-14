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
