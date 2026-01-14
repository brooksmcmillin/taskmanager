"""Database connection and session management."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# Create async engine
_engine = create_async_engine(
    settings.database_url,
    echo=not settings.is_production,
    pool_pre_ping=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def get_engine():
    """Get the database engine."""
    return _engine


async def init_db() -> None:
    """Initialize database tables.

    Note: In production, use Alembic migrations instead.
    """
    async with _engine.begin() as conn:
        # Import all models to ensure they're registered
        from app.models import (  # noqa: F401
            user,
            session,
            todo,
            project,
            oauth,
            recurring_task,
        )

        await conn.run_sync(Base.metadata.create_all)
