"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.db.database import Base

# Import all models to ensure they're registered with Base.metadata
from app.models import oauth, project, recurring_task, session, todo, user  # noqa: F401

config = context.config

# Set the database URL from settings
# Escape % signs for ConfigParser (% -> %%)
escaped_url = settings.database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", escaped_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def ensure_version_table_width(connection) -> None:
    """Ensure alembic_version.version_num can hold longer revision IDs.

    Alembic defaults to varchar(32) which is too short for descriptive revision IDs.
    This creates the table with varchar(128) if it doesn't exist, or widens the
    column if it does exist with a smaller width.
    """
    connection.execute(
        text("""
        DO $$
        BEGIN
            -- Create table with wider column if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'alembic_version'
            ) THEN
                CREATE TABLE alembic_version (
                    version_num VARCHAR(128) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                );
            -- Widen existing column if needed
            ELSIF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'alembic_version'
                AND column_name = 'version_num'
                AND character_maximum_length < 128
            ) THEN
                ALTER TABLE alembic_version
                ALTER COLUMN version_num TYPE varchar(128);
            END IF;
        END $$;
    """)
    )
    connection.commit()


def do_run_migrations(connection) -> None:
    """Run migrations with connection."""
    ensure_version_table_width(connection)
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
