"""Add is_featured column to feed_sources table.

Revision ID: 0016_add_is_featured_to_feed_sources
Revises: 0015_remove_username
Create Date: 2026-02-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_add_is_featured_to_feed_sources"
down_revision: str | None = "0015_remove_username"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feed_sources",
        sa.Column("is_featured", sa.Boolean(), nullable=True),
    )
    op.execute("UPDATE feed_sources SET is_featured = false")
    op.alter_column("feed_sources", "is_featured", nullable=False)


def downgrade() -> None:
    op.drop_column("feed_sources", "is_featured")
