"""Add subtasks support via parent_id field on todos.

This migration adds:
1. parent_id column to todos table for hierarchical subtasks
2. Index on parent_id for efficient subtask queries

Revision ID: 0004_add_subtasks
Revises: ffb35ffdc790
Create Date: 2026-01-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_add_subtasks"
down_revision: str | None = "ffb35ffdc790"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add parent_id column to todos table for subtasks."""
    op.add_column(
        "todos",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_todos_parent_id",
        "todos",
        "todos",
        ["parent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_todos_parent_id", "todos", ["parent_id"])


def downgrade() -> None:
    """Remove parent_id column from todos table."""
    op.drop_index("ix_todos_parent_id", table_name="todos")
    op.drop_constraint("fk_todos_parent_id", "todos", type_="foreignkey")
    op.drop_column("todos", "parent_id")
