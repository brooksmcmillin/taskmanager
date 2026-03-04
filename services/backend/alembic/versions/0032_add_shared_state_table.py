"""Add shared_state table for multi-worker rate limiting and OAuth state

Revision ID: 0032_add_shared_state_table
Revises: 0031_add_event_bus_triggers
Create Date: 2026-03-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0032_add_shared_state_table"
down_revision: str | None = "0031_add_event_bus_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shared_state",
        sa.Column("namespace", sa.String(50), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("namespace", "key"),
    )
    op.create_index("ix_shared_state_expires_at", "shared_state", ["expires_at"])
    op.create_index(
        "ix_shared_state_namespace_expires",
        "shared_state",
        ["namespace", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_shared_state_namespace_expires", table_name="shared_state")
    op.drop_index("ix_shared_state_expires_at", table_name="shared_state")
    op.drop_table("shared_state")
