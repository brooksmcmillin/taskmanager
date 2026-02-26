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
from sqlalchemy import text  # noqa: E402
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


def _get_db_name(worker_id: str) -> str:
    """Return per-worker database name for xdist, or default for single-process."""
    if worker_id == "master":
        return "taskmanager_test"
    # worker_id is "gw0", "gw1", etc.
    return f"taskmanager_test_{worker_id}"


def _make_database_url(db_name: str) -> str:
    """Build async database URL for the given database name."""
    return f"postgresql+asyncpg://{POSTGRES_USER}:{encoded_password}@{POSTGRES_HOST}:{POSTGRES_PORT}/{db_name}"


@pytest.fixture(scope="session")
def worker_db_name(worker_id: str) -> str:
    """Return the database name for this xdist worker."""
    return _get_db_name(worker_id)


@pytest.fixture(scope="session", autouse=True)
def _create_worker_database(worker_db_name: str):
    """Create a per-worker database at session start, drop it at session end.

    Uses synchronous psycopg to avoid async event loop issues in session fixtures.
    """
    if worker_db_name == "taskmanager_test":
        # Single-process mode — assume database already exists (CI creates it)
        yield
        return

    import psycopg

    conninfo = (
        f"host={POSTGRES_HOST} port={POSTGRES_PORT} "
        f"user={POSTGRES_USER} password={POSTGRES_PASSWORD} "
        f"dbname=taskmanager_test"
    )

    # CREATE/DROP DATABASE cannot run inside a transaction
    conn = psycopg.connect(conninfo, autocommit=True)
    try:
        conn.execute(f"DROP DATABASE IF EXISTS {worker_db_name}")
        conn.execute(f"CREATE DATABASE {worker_db_name}")
    finally:
        conn.close()

    yield

    conn = psycopg.connect(conninfo, autocommit=True)
    try:
        conn.execute(f"DROP DATABASE IF EXISTS {worker_db_name}")
    finally:
        conn.close()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_engine(worker_db_name: str):
    """Create test database engine."""
    engine = create_async_engine(_make_database_url(worker_db_name), echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        # Drop all tables with CASCADE to handle FK dependencies from
        # tables created by migrations but not in ORM metadata (e.g.
        # mcp_access_tokens, mcp_refresh_tokens).
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

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
        json={"email": "test@example.com", "password": TEST_USER_PASSWORD},
    )
    assert response.status_code == 200

    # Client now has session cookie
    return client
