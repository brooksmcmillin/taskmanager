"""Add deadline_type field to todos table.

Adds a deadline_type column to indicate how strictly a task's due date
should be respected:
- flexible: Due date is a loose suggestion; reschedule freely.
- preferred: Soft target date; try to hit it but okay to slip (default).
- firm: Avoid moving unless necessary (e.g., external dependency).
- hard: Immovable deadline; never reschedule (e.g., legal, contractual).

Existing rows default to 'preferred' for backward compatibility.

Revision ID: 0020_add_deadline_type
Revises: 0019_add_updated_at_server_default
Create Date: 2026-02-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_add_deadline_type"
down_revision: str | None = "0019_add_updated_at_server_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add deadline_type column to todos table."""
    op.add_column(
        "todos",
        sa.Column(
            "deadline_type",
            sa.String(20),
            nullable=False,
            server_default="preferred",
        ),
    )

    # Create index for filtering by deadline type
    op.create_index("ix_todos_deadline_type", "todos", ["deadline_type"])


def downgrade() -> None:
    """Remove deadline_type column from todos table."""
    op.drop_index("ix_todos_deadline_type", table_name="todos")
    op.drop_column("todos", "deadline_type")
