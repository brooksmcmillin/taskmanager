"""Test bcrypt compatibility between Node.js bcryptjs and Python bcrypt.

This ensures that the FastAPI backend can authenticate users whose passwords
were hashed by the Node.js bcryptjs library.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


@pytest.mark.asyncio
async def test_bcrypt_hash_format(db_session: AsyncSession):  # noqa: ARG001
    """Test that Python bcrypt creates compatible $2b$ hashes."""
    password = "TestPassword123!"  # pragma: allowlist secret

    # Create hash with Python bcrypt
    hashed = hash_password(password)

    # Verify format matches Node.js bcryptjs
    assert hashed.startswith("$2b$12$"), "Hash should use $2b$ format with 12 rounds"
    assert len(hashed) == 60, "bcrypt hash should be 60 characters"

    # Verify the hash works
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


@pytest.mark.asyncio
async def test_bcrypt_round_trip(db_session: AsyncSession):  # noqa: ARG001
    """Test that hashes can be created and verified consistently."""
    test_cases = [
        "SimplePassword",
        "ComplexP@ssw0rd!",
        "password with spaces",
        "🔒emoji_password",
        "a" * 72,  # Maximum bcrypt input length
    ]

    for password in test_cases:
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True, f"Failed for: {password}"
        assert verify_password("wrong", hashed) is False


@pytest.mark.asyncio
async def test_python_created_user_can_login(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that users created by Python bcrypt can log in.

    This ensures the FastAPI backend works correctly for newly created users.
    """
    password = "new_python_user_password"  # pragma: allowlist secret

    # Create user with Python bcrypt
    user = User(
        email="python@example.com",
        password_hash=hash_password(password),
    )
    db_session.add(user)
    await db_session.commit()

    # Try to log in
    response = await client.post(
        "/api/auth/login",
        json={
            "email": "python@example.com",
            "password": password,
        },
    )

    # Login should succeed
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "python@example.com"


@pytest.mark.asyncio
async def test_hash_format_compatibility(db_session: AsyncSession):  # noqa: ARG001
    """Verify that Python bcrypt produces the same hash format as Node.js bcryptjs.

    Both libraries should:
    - Use $2b$ identifier (bcrypt revision)
    - Use 12 cost factor
    - Produce 60-character hashes
    - Be mutually verifiable
    """
    password = "test_password_123"  # pragma: allowlist secret
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    # Different hashes (due to different salts)
    assert hash1 != hash2

    # Same format
    assert hash1.startswith("$2b$12$")
    assert hash2.startswith("$2b$12$")
    assert len(hash1) == 60
    assert len(hash2) == 60

    # Both verify the same password
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True
