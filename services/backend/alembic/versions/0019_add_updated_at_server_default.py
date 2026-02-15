"""Add server_default to updated_at columns and backfill NULLs.

Revision ID: 0019_add_updated_at_server_default
Revises: 0018_add_is_featured_index
Create Date: 2026-02-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019_add_updated_at_server_default"
down_revision: str | None = "0018_add_is_featured_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing NULL updated_at rows with created_at
    op.execute("UPDATE todos SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute("UPDATE comments SET updated_at = created_at WHERE updated_at IS NULL")

    # Add server_default so new rows get updated_at = now()
    op.alter_column(
        "todos",
        "updated_at",
        server_default=sa.func.now(),
    )
    op.alter_column(
        "comments",
        "updated_at",
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.alter_column(
        "todos",
        "updated_at",
        server_default=None,
    )
    op.alter_column(
        "comments",
        "updated_at",
        server_default=None,
    )
