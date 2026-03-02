"""Add bookmark fields to article_interactions

Revision ID: 0028_add_bookmarks
Revises: 0027_add_show_on_calendar_to_projects
Create Date: 2026-03-01

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028_add_bookmarks"
down_revision: str | None = "0027_add_show_on_calendar_to_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "article_interactions",
        sa.Column(
            "is_bookmarked", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "article_interactions",
        sa.Column("bookmarked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("article_interactions", "bookmarked_at")
    op.drop_column("article_interactions", "is_bookmarked")
