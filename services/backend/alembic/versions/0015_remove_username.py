"""Remove username column from users table.

Use email as the sole user identifier for login, display, and API interactions.

Revision ID: 0015_remove_username
Revises: 0014_add_oauth_providers
Create Date: 2026-02-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015_remove_username"
down_revision: str | None = "0014_add_oauth_providers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop index if it exists (may not exist in all environments)
    op.execute("DROP INDEX IF EXISTS ix_users_username")
    op.drop_column("users", "username")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "username",
            sa.String(length=255),
            nullable=True,
        ),
    )
    # Populate username from email prefix + id to ensure uniqueness
    op.execute("UPDATE users SET username = CONCAT(SPLIT_PART(email, '@', 1), '_', id)")
    op.alter_column("users", "username", nullable=False)
    op.create_index("ix_users_username", "users", ["username"], unique=True)
