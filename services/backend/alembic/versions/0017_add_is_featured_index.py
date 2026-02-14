"""Add index on feed_sources.is_featured for filter queries.

Revision ID: 0017_add_is_featured_index
Revises: 0016_add_is_featured_to_feed_sources
Create Date: 2026-02-14

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_add_is_featured_index"
down_revision: str | None = "0016_add_is_featured_to_feed_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_feed_sources_is_featured"), "feed_sources", ["is_featured"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feed_sources_is_featured"), table_name="feed_sources")
