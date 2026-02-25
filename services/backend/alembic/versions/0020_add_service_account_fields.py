"""Add service account fields to users table.

Revision ID: 0020_add_service_account_fields
Revises: 0019_add_updated_at_server_default
Create Date: 2026-02-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020_add_service_account_fields"
down_revision: str | None = "0019_add_updated_at_server_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_service_account",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
    op.drop_column("users", "is_service_account")
