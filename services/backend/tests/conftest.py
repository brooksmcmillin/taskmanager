"""Pytest fixtures for testing."""

# IMPORTANT: Set environment variables BEFORE importing any app modules
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root (two directories up from tests/)
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

# Disable registration codes for testing
os.environ["REGISTRATION_CODE_REQUIRED"] = "false"

# Set frontend URL for testing
os.environ["FRONTEND_URL"] = "http://localhost:3000"

import asyncio  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402
from urllib.parse import quote_plus  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.rate_limit import login_rate_limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.database import Base  # noqa: E402
from app.dependencies import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

# Use a separate test database
# Read credentials from environment variables, same as production
POSTGRES_USER = os.getenv("POSTGRES_USER", "taskmanager")
POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD", "taskmanager"
)  # pragma: allowlist secret
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# URL-encode the password to handle special characters

encoded_password = quote_plus(POSTGRES_PASSWORD)

TEST_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/taskmanager_test"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Reset rate limiter before each test
    login_rate_limiter._attempts.clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    # Reset rate limiter after each test
    login_rate_limiter._attempts.clear()


TEST_USER_PASSWORD = "TestPass123!"  # pragma: allowlist secret


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=hash_password(TEST_USER_PASSWORD),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_client(
    client: AsyncClient,
    test_user: User,
) -> AsyncClient:
    """Create authenticated test client."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200

    # Client now has session cookie
    return client
