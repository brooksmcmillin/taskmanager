"""Tests for registration code functionality and race condition prevention."""

import asyncio

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select

from app.models.registration_code import RegistrationCode
from app.models.user import User

TEST_PASSWORD = "SecurePass123!"  # pragma: allowlist secret


@pytest.fixture
async def registration_code(db_session):
    """Create a test registration code with max_uses=1."""
    code = RegistrationCode(
        code="TEST-CODE-001",
        max_uses=1,
        current_uses=0,
        is_active=True,
    )
    db_session.add(code)
    await db_session.commit()
    await db_session.refresh(code)
    return code


@pytest.mark.asyncio
async def test_registration_code_race_condition_prevention(
    client: AsyncClient, db_session, registration_code
):
    """Test that concurrent registrations with same code don't exceed max_uses.

    This test verifies the fix for the race condition where multiple concurrent
    registration requests could all validate the same code and then increment
    the usage counter, allowing more registrations than max_uses.
    """
    # Override settings to require registration codes for this test
    from app.config import settings

    original_value = settings.registration_code_required
    settings.registration_code_required = True

    try:
        # Create 5 concurrent registration requests using the same code (max_uses=1)
        async def register_user(email: str):
            return await client.post(
                "/api/auth/register",
                json={
                    "email": email,
                    "password": TEST_PASSWORD,
                    "registration_code": registration_code.code,
                },
            )

        # Run 5 concurrent registrations
        tasks = [register_user(f"user{i}@example.com") for i in range(5)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful registrations (201) vs failed (400/409/422)
        success_count = sum(
            1 for r in responses if isinstance(r, Response) and r.status_code == 201
        )

        # Verify exactly 1 registration succeeded (matching max_uses=1)
        assert (
            success_count == 1
        ), f"Expected 1 successful registration, got {success_count}"

        # Verify the registration code usage was incremented correctly
        result = await db_session.execute(
            select(RegistrationCode).where(
                RegistrationCode.code == registration_code.code
            )
        )
        updated_code = result.scalar_one()
        assert (
            updated_code.current_uses == 1
        ), f"Expected current_uses=1, got {updated_code.current_uses}"

        # Verify only 1 user was created
        result = await db_session.execute(select(User))
        users = result.scalars().all()
        new_users = [
            u for u in users if u.email.startswith("user")
        ]  # Filter to our test users
        assert len(new_users) == 1, f"Expected 1 user created, got {len(new_users)}"

    finally:
        # Restore original setting
        settings.registration_code_required = original_value


@pytest.mark.asyncio
async def test_registration_code_required_when_enabled(
    client: AsyncClient, registration_code
):
    """Test that registration requires a code when REGISTRATION_CODE_REQUIRED=true."""
    from app.config import settings

    original_value = settings.registration_code_required
    settings.registration_code_required = True

    try:
        # Attempt registration without code
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": TEST_PASSWORD,
            },
        )

        assert response.status_code == 400  # Registration code required error

    finally:
        settings.registration_code_required = original_value


@pytest.mark.asyncio
async def test_registration_code_not_required_when_disabled(client: AsyncClient):
    """Test registration without code when REGISTRATION_CODE_REQUIRED=false."""
    from app.config import settings

    original_value = settings.registration_code_required
    settings.registration_code_required = False

    try:
        # Register without code
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test2@example.com",
                "password": TEST_PASSWORD,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "test2@example.com"

    finally:
        settings.registration_code_required = original_value


@pytest.mark.asyncio
async def test_registration_code_validates_correctly(
    client: AsyncClient, registration_code
):
    """Test that registration code validation works correctly."""
    from app.config import settings

    original_value = settings.registration_code_required
    settings.registration_code_required = True

    try:
        # Test with valid code
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "valid@example.com",
                "password": TEST_PASSWORD,
                "registration_code": registration_code.code,
            },
        )
        assert response.status_code == 201

        # Test with invalid code (should fail - code is exhausted)
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "invalid@example.com",
                "password": TEST_PASSWORD,
                "registration_code": registration_code.code,
            },
        )
        assert response.status_code in [400, 409, 422]  # Code exhausted or invalid

        # Test with non-existent code
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "none@example.com",
                "password": TEST_PASSWORD,
                "registration_code": "NONEXISTENT",
            },
        )
        assert response.status_code in [400, 422]  # Invalid code

    finally:
        settings.registration_code_required = original_value
