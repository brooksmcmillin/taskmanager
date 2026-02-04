"""Add partial index for project stats queries.

This migration adds a partial composite index on todos table
to optimize the project statistics aggregation query.

Revision ID: 0013_add_project_stats_index
Revises: 0012_add_webauthn_credentials
Create Date: 2026-02-04

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_add_project_stats_index"
down_revision: str | None = "0012_add_webauthn_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add partial index for project stats queries.

    This index optimizes the common query pattern:
    - Filter by project_id
    - Only top-level tasks (parent_id IS NULL)
    - Only non-deleted tasks (deleted_at IS NULL)
    """
    op.create_index(
        "ix_todos_project_stats",
        "todos",
        ["project_id", "status"],
        postgresql_where="deleted_at IS NULL AND parent_id IS NULL",
    )


def downgrade() -> None:
    """Remove the project stats index."""
    op.drop_index("ix_todos_project_stats", table_name="todos")
