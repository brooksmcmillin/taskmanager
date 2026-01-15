"""Pytest fixtures for testing."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.database import Base
from app.dependencies import get_db
from app.core.security import hash_password
from app.models.user import User


# Use a separate test database
import os

# Read credentials from environment variables, same as production
POSTGRES_USER = os.getenv("POSTGRES_USER", "taskmanager")
POSTGRES_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD", "taskmanager"
)  # pragma: allowlist secret
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# URL-encode the password to handle special characters
from urllib.parse import quote_plus

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

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


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
