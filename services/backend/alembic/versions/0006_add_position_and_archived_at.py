"""Add position and archived_at fields for ordering support.

This migration adds:
1. position field to projects table for manual ordering
2. archived_at field to projects table for soft archive
3. position field to todos table for manual ordering within projects/parents

Revision ID: 0006_add_position_and_archived_at
Revises: 9103b4db1955
Create Date: 2026-01-31

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_position_and_archived_at"
down_revision: str | None = "9103b4db1955"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add position and archived_at columns."""
    # Add position column to projects table
    op.add_column(
        "projects",
        sa.Column("position", sa.Integer(), nullable=True),
    )
    # Set default position values based on existing order (by name)
    op.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY name) - 1 as pos
            FROM projects
        )
        UPDATE projects
        SET position = ranked.pos
        FROM ranked
        WHERE projects.id = ranked.id
    """)
    # Make position NOT NULL with default
    op.alter_column("projects", "position", nullable=False, server_default="0")

    # Add archived_at column to projects table
    op.add_column(
        "projects",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Add position column to todos table
    op.add_column(
        "todos",
        sa.Column("position", sa.Integer(), nullable=True),
    )
    # Set default position values based on existing order (by created_at)
    op.execute("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id, COALESCE(parent_id, 0)
                ORDER BY created_at
            ) - 1 as pos
            FROM todos
        )
        UPDATE todos
        SET position = ranked.pos
        FROM ranked
        WHERE todos.id = ranked.id
    """)
    # Make position NOT NULL with default
    op.alter_column("todos", "position", nullable=False, server_default="0")

    # Add indexes for efficient ordering queries
    op.create_index("ix_projects_position", "projects", ["user_id", "position"])
    op.create_index("ix_todos_position", "todos", ["user_id", "parent_id", "position"])


def downgrade() -> None:
    """Remove position and archived_at columns."""
    op.drop_index("ix_todos_position", table_name="todos")
    op.drop_index("ix_projects_position", table_name="projects")
    op.drop_column("todos", "position")
    op.drop_column("projects", "archived_at")
    op.drop_column("projects", "position")
