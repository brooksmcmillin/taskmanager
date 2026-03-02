"""add wiki parent_id and tags columns

Revision ID: 0025_add_wiki_parent_id_and_tags
Revises: 0024_project_name_unique_per_user
Create Date: 2026-02-27 00:00:00.000000

Adds parent_id (self-referential FK) for hierarchical wiki pages
and tags (JSONB) for categorization.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025_add_wiki_parent_id_and_tags"
down_revision: str | None = "0024_project_name_unique_per_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "wiki_pages",
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_wiki_pages_parent_id", "wiki_pages", ["parent_id"])

    op.add_column(
        "wiki_pages",
        sa.Column(
            "tags",
            JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("wiki_pages", "tags")
    op.drop_index("ix_wiki_pages_parent_id", table_name="wiki_pages")
    op.drop_column("wiki_pages", "parent_id")
