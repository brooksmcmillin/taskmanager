"""Initial schema matching existing database.

This migration represents the complete schema as it exists in the production
database (created by Node.js SQL migrations). For existing databases, use:
    alembic stamp head
to mark this migration as already applied without running it.

For fresh databases (e.g., testing), run:
    alembic upgrade head
to create all tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all tables."""
    # Enable uuid-ossp extension (used by original schema)
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create update_updated_at_column trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
        END;
        $$ language 'plpgsql'
    """)

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Create sessions table
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sessions_user", "sessions", ["user_id"])
    op.create_index("idx_sessions_expires", "sessions", ["expires_at"])

    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "color", sa.String(length=7), server_default="#3b82f6", nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("idx_projects_user", "projects", ["user_id"])

    # Create recurring_tasks table
    op.create_table(
        "recurring_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("interval_value", sa.Integer(), server_default="1", nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority", sa.String(length=20), server_default="medium", nullable=False
        ),
        sa.Column("estimated_hours", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("context", sa.String(length=50), nullable=True),
        sa.Column("skip_missed", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly', 'yearly')",
            name="recurring_tasks_frequency_check",
        ),
        sa.CheckConstraint(
            "interval_value >= 1", name="recurring_tasks_interval_check"
        ),
        sa.CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name="recurring_tasks_day_of_month_check",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="recurring_tasks_priority_check",
        ),
    )
    op.create_index("idx_recurring_tasks_user", "recurring_tasks", ["user_id"])
    op.create_index(
        "idx_recurring_tasks_next_due",
        "recurring_tasks",
        ["next_due_date"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "idx_recurring_tasks_active",
        "recurring_tasks",
        ["user_id", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # Create todos table
    op.create_table(
        "todos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("recurring_task_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "priority", sa.String(length=20), server_default="medium", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_hours", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("actual_hours", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("tags", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("context", sa.String(length=50), nullable=True),
        sa.Column("time_horizon", sa.String(length=20), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["recurring_task_id"], ["recurring_tasks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="todos_priority_check",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="todos_status_check",
        ),
        sa.CheckConstraint(
            "time_horizon IN ('today', 'this_week', 'next_week', 'this_month', "
            "'next_month', 'this_quarter', 'next_quarter', 'this_year', "
            "'next_year', 'someday')",
            name="todos_time_horizon_check",
        ),
    )
    op.create_index("idx_todos_user", "todos", ["user_id"])
    op.create_index("idx_todos_project", "todos", ["project_id"])
    op.create_index("idx_todos_status", "todos", ["status"])
    op.create_index("idx_todos_priority", "todos", ["priority"])
    op.create_index("idx_todos_due_date", "todos", ["due_date"])
    op.create_index("idx_todos_time_horizon", "todos", ["time_horizon"])
    op.create_index("idx_todos_deleted_at", "todos", ["deleted_at"])
    op.create_index(
        "idx_todos_recurring",
        "todos",
        ["recurring_task_id"],
        postgresql_where=sa.text("recurring_task_id IS NOT NULL"),
    )
    # GIN index for tags
    op.create_index(
        "idx_todos_tags",
        "todos",
        ["tags"],
        postgresql_using="gin",
    )
    # Full-text search index
    op.execute("""
        CREATE INDEX idx_todos_search ON todos USING GIN(
            to_tsvector('english', title || ' ' || COALESCE(description, ''))
        )
    """)

    # Create oauth_clients table
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column(
            "grant_types",
            sa.Text(),
            server_default='["authorization_code"]',
            nullable=False,
        ),
        sa.Column("scopes", sa.Text(), server_default='["read"]', nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_index(
        "ix_oauth_clients_client_id", "oauth_clients", ["client_id"], unique=True
    )
    op.create_index("idx_oauth_clients_user_id", "oauth_clients", ["user_id"])

    # Create authorization_codes table
    op.create_table(
        "authorization_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=500), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("code_challenge", sa.String(length=255), nullable=True),
        sa.Column("code_challenge_method", sa.String(length=10), nullable=True),
        sa.Column("used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "ix_authorization_codes_code", "authorization_codes", ["code"], unique=True
    )
    op.create_index(
        "idx_authorization_codes_client_id", "authorization_codes", ["client_id"]
    )

    # Create access_tokens table
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("refresh_token", sa.String(length=255), nullable=False),
        sa.Column(
            "refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        sa.UniqueConstraint("refresh_token"),
    )
    op.create_index("ix_access_tokens_token", "access_tokens", ["token"], unique=True)
    op.create_index(
        "ix_access_tokens_refresh_token",
        "access_tokens",
        ["refresh_token"],
        unique=True,
    )
    op.create_index("idx_access_tokens_client_id", "access_tokens", ["client_id"])

    # Create device_authorization_codes table
    op.create_table(
        "device_authorization_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_code", sa.String(length=255), nullable=False),
        sa.Column("user_code", sa.String(length=16), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("interval", sa.Integer(), server_default="5", nullable=False),
        sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_code"),
        sa.UniqueConstraint("user_code"),
    )
    op.create_index(
        "ix_device_authorization_codes_device_code",
        "device_authorization_codes",
        ["device_code"],
        unique=True,
    )
    op.create_index(
        "ix_device_authorization_codes_user_code",
        "device_authorization_codes",
        ["user_code"],
        unique=True,
    )
    op.create_index(
        "idx_device_auth_codes_status", "device_authorization_codes", ["status"]
    )
    op.create_index(
        "idx_device_auth_codes_expires_at", "device_authorization_codes", ["expires_at"]
    )
    op.create_index(
        "idx_device_auth_codes_client_id", "device_authorization_codes", ["client_id"]
    )

    # Create update triggers (matching original schema)
    op.execute("""
        CREATE TRIGGER update_users_updated_at
          BEFORE UPDATE ON users
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)
    op.execute("""
        CREATE TRIGGER update_projects_updated_at
          BEFORE UPDATE ON projects
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)
    op.execute("""
        CREATE TRIGGER update_todos_updated_at
          BEFORE UPDATE ON todos
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)
    op.execute("""
        CREATE TRIGGER update_recurring_tasks_updated_at
          BEFORE UPDATE ON recurring_tasks
          FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    """Drop all tables."""
    # Drop triggers
    op.execute(
        "DROP TRIGGER IF EXISTS update_recurring_tasks_updated_at ON recurring_tasks"
    )
    op.execute("DROP TRIGGER IF EXISTS update_todos_updated_at ON todos")
    op.execute("DROP TRIGGER IF EXISTS update_projects_updated_at ON projects")
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")

    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table("device_authorization_codes")
    op.drop_table("access_tokens")
    op.drop_table("authorization_codes")
    op.drop_table("oauth_clients")
    op.drop_table("todos")
    op.drop_table("recurring_tasks")
    op.drop_table("projects")
    op.drop_table("sessions")
    op.drop_table("users")

    # Drop trigger function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
