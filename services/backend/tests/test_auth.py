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
            "email": "new@example.com",
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Registration successful"
    assert data["user"]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    """Test registration with existing email."""
    response = await client.post(
        "/api/auth/register",
        json={
            "email": "test@example.com",  # Already exists
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CONFLICT_002"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Test registration with weak password."""
    response = await client.post(
        "/api/auth/register",
        json={
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
        json={"email": "test@example.com", "password": TEST_PASSWORD_LOGIN},
    )

    assert response.status_code == 200
    assert "session" in response.cookies
    data = response.json()
    assert data["message"] == "Login successful"
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, test_user):
    """Test login with wrong password."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
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
    login_rate_limiter.reset("test@example.com")

    # Make 5 failed login attempts
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # 6th attempt should be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
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
            json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # Successful login should reset the counter
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": TEST_PASSWORD_LOGIN},
    )
    assert response.status_code == 200

    # Now we should be able to make failed attempts again without being rate limited
    for _ in range(3):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_per_email(client: AsyncClient, test_user):
    """Test that rate limiting is per email, not global."""
    # Make 5 failed attempts for test@example.com
    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
        )
        assert response.status_code == 401

    # test@example.com should be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": TEST_PASSWORD_WRONG},
    )
    assert response.status_code == 429

    # But a different email should not be rate limited
    response = await client.post(
        "/api/auth/login",
        json={"email": "other@example.com", "password": TEST_PASSWORD_WRONG},
    )
    assert response.status_code == 401  # Invalid credentials, not rate limited


# =============================================================================
# Form-based Login Tests (OAuth Flows)
# =============================================================================


@pytest.mark.asyncio
async def test_login_form_data_success(client: AsyncClient, test_user):
    """Test successful login using form data instead of JSON."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200
    assert "session" in response.cookies
    data = response.json()
    assert data["message"] == "Login successful"
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login_form_data_with_return_to(client: AsyncClient, test_user):
    """Test form-based login with return_to parameter for OAuth callback."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "/oauth/callback?code=abc123",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    # Should redirect, not return JSON
    assert response.status_code == 302
    assert response.headers["location"] == "/oauth/callback?code=abc123"

    # Verify session cookie is set in redirect response
    assert "session" in response.cookies


@pytest.mark.asyncio
async def test_login_form_data_return_to_prevents_open_redirect(
    client: AsyncClient, test_user
):
    """Test that return_to validation prevents open redirect attacks."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "https://evil.com/phishing",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Should reject with validation error, not redirect
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_009"
    assert "redirect" in response.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_login_form_data_return_to_rejects_absolute_url(
    client: AsyncClient, test_user
):
    """Test that return_to rejects absolute URLs even for same origin."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "http://localhost:3000/dashboard",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Absolute URLs (even same-origin) are rejected; only relative paths allowed
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_009"


@pytest.mark.asyncio
async def test_login_form_data_return_to_relative_path(client: AsyncClient, test_user):
    """Test that return_to allows relative paths starting with /."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "/oauth/callback",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    # Relative paths starting with / should be allowed
    assert response.status_code == 302
    assert response.headers["location"] == "/oauth/callback"


@pytest.mark.asyncio
async def test_login_form_data_return_to_protocol_relative_rejected(
    client: AsyncClient, test_user
):
    """Test that return_to rejects protocol-relative URLs (//evil.com bypass)."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "//evil.com/phishing",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Protocol-relative URLs must be rejected to prevent open redirect
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_009"
    assert "redirect" in response.json()["detail"]["message"].lower()


@pytest.mark.asyncio
async def test_login_form_data_return_to_root_path_allowed(
    client: AsyncClient, test_user
):
    """Test that return_to allows the root path /."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "/",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/"


@pytest.mark.asyncio
async def test_login_form_data_return_to_dashboard_allowed(
    client: AsyncClient, test_user
):
    """Test that return_to allows a normal dashboard path."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "/dashboard",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/dashboard"


@pytest.mark.asyncio
async def test_login_form_data_return_to_tasks_path_allowed(
    client: AsyncClient, test_user
):
    """Test that return_to allows a nested task path."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "/tasks/123",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/tasks/123"


@pytest.mark.asyncio
async def test_login_form_data_return_to_empty_string(client: AsyncClient, test_user):
    """Test that an empty return_to is treated as absent (no redirect)."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    # Empty return_to is falsy, so no redirect — returns JSON login response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Login successful"


@pytest.mark.asyncio
async def test_login_form_data_return_to_no_leading_slash_rejected(
    client: AsyncClient, test_user
):
    """Test that return_to without a leading / is rejected."""
    response = await client.post(
        "/api/auth/login",
        data={
            "email": "test@example.com",
            "password": TEST_PASSWORD_LOGIN,
            "return_to": "dashboard",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_009"


@pytest.mark.asyncio
async def test_login_unsupported_content_type(client: AsyncClient, test_user):
    """Test login with unsupported content type."""
    response = await client.post(
        "/api/auth/login",
        content=b"email=test@example.com&password=test",
        headers={"Content-Type": "text/plain"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_001"
