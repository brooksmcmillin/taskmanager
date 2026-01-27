#!/usr/bin/env python3
"""Reset the test database for E2E tests."""

import os
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Settings directly and bypass cache
from app.config import Settings


def reset_test_database():
    """Drop and recreate all tables in the test database."""
    # Create fresh settings instance with .env.test
    # Settings will load from environment variables set by start script
    settings = Settings()

    # Verify we're using test database
    if not settings.postgres_db.endswith("_test"):
        print(f"ERROR: Refusing to reset non-test database: {settings.postgres_db}")
        sys.exit(1)

    print(f"Resetting test database: {settings.postgres_db}")

    # Check if we should use Docker (postgres user doesn't exist locally)
    use_docker = subprocess.run(
        ["id", "-u", "postgres"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode != 0

    if use_docker:
        # Use Docker exec to run psql commands
        container_name = "postgres_db"

        # Drop database
        drop_cmd = [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            settings.postgres_user,
            "-d",
            "postgres",
            "-c",
            f"DROP DATABASE IF EXISTS {settings.postgres_db}",
        ]

        # Create database
        create_cmd = [
            "docker",
            "exec",
            container_name,
            "psql",
            "-U",
            settings.postgres_user,
            "-d",
            "postgres",
            "-c",
            f"CREATE DATABASE {settings.postgres_db}",
        ]

        # Grant permissions (not needed when using same user)
        grant_db_cmd = None
        grant_schema_cmd = None
    else:
        # Use sudo to run psql as postgres user (local install)
        # Drop database
        drop_cmd = [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-p",
            str(settings.postgres_port),
            "-c",
            f"DROP DATABASE IF EXISTS {settings.postgres_db}",
        ]

        # Create database
        create_cmd = [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-p",
            str(settings.postgres_port),
            "-c",
            f"CREATE DATABASE {settings.postgres_db}",
        ]

        # Grant permissions
        db_name = settings.postgres_db
        db_user = settings.postgres_user
        grant_sql = (
            f"ALTER DATABASE {db_name} OWNER TO {db_user}; "
            f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user}"
        )
        grant_db_cmd = [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-p",
            str(settings.postgres_port),
            "-c",
            grant_sql,
        ]

        grant_schema_cmd = [
            "sudo",
            "-u",
            "postgres",
            "psql",
            "-p",
            str(settings.postgres_port),
            "-d",
            settings.postgres_db,
            "-c",
            f"GRANT ALL ON SCHEMA public TO {settings.postgres_user}",
        ]

    try:
        # Drop
        result = subprocess.run(drop_cmd, capture_output=True, text=True)
        if result.returncode != 0 and "does not exist" not in result.stderr:
            print(f"Warning: Drop database failed: {result.stderr}")
        else:
            print(f"Dropped database {settings.postgres_db}")

        # Create
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=True)
        print(f"Created database {settings.postgres_db}")

        # Grant permissions (only for local postgres)
        if grant_db_cmd and grant_schema_cmd:
            subprocess.run(grant_db_cmd, capture_output=True, text=True, check=True)
            subprocess.run(grant_schema_cmd, capture_output=True, text=True, check=True)
            print(f"Granted permissions to {settings.postgres_user}")

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to create database: {e.stderr}")
        sys.exit(1)

    # Run migrations with test environment
    print("Running migrations...")
    env = os.environ.copy()

    # Read .env.test and set environment variables for Alembic
    env_test_path = Path(__file__).parent.parent / ".env.test"
    with open(env_test_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=Path(__file__).parent.parent,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✓ Test database reset complete")
    else:
        print(f"✗ Migration failed: {result.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    reset_test_database()
