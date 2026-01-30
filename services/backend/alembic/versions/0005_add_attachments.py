"""Add attachments table for todo image uploads.

This migration adds:
1. attachments table with todo_id and user_id foreign keys
2. Indexes on todo_id and user_id for efficient queries
3. Cascade delete when parent todo or user is deleted

Revision ID: 0005_add_attachments
Revises: 0004_add_subtasks
Create Date: 2026-01-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_add_attachments"
down_revision: str | None = "0004_add_subtasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create attachments table."""
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("todo_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["todo_id"],
            ["todos.id"],
            name="fk_attachments_todo_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_attachments_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_attachments_todo_id", "attachments", ["todo_id"])
    op.create_index("ix_attachments_user_id", "attachments", ["user_id"])


def downgrade() -> None:
    """Drop attachments table."""
    op.drop_index("ix_attachments_user_id", table_name="attachments")
    op.drop_index("ix_attachments_todo_id", table_name="attachments")
    op.drop_table("attachments")
