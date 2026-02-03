"""Add autonomy_tier field to todos table.

This migration adds the autonomy_tier field for autonomous agent task execution:
- Tier 1: Fully autonomous (read-only, no side effects)
- Tier 2: Propose & execute (async notification, can be reverted)
- Tier 3: Propose & wait (explicit approval before execution)
- Tier 4: Never autonomous (always human-executed)

Revision ID: 0010_add_autonomy_tier
Revises: 0009_add_api_keys_composite_index
Create Date: 2026-02-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_add_autonomy_tier"
down_revision: str | None = "0009_add_api_keys_composite_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add autonomy_tier field to todos table."""
    # autonomy_tier - integer field for risk level (1-4)
    op.add_column(
        "todos",
        sa.Column("autonomy_tier", sa.Integer(), nullable=True),
    )

    # Create index on autonomy_tier for efficient filtering
    op.create_index("ix_todos_autonomy_tier", "todos", ["autonomy_tier"])

    # Add check constraint to ensure valid range (1-4)
    op.create_check_constraint(
        "ck_todos_autonomy_tier_range",
        "todos",
        "autonomy_tier IS NULL OR (autonomy_tier >= 1 AND autonomy_tier <= 4)",
    )


def downgrade() -> None:
    """Remove autonomy_tier field from todos table."""
    op.drop_constraint("ck_todos_autonomy_tier_range", "todos", type_="check")
    op.drop_index("ix_todos_autonomy_tier", table_name="todos")
    op.drop_column("todos", "autonomy_tier")
