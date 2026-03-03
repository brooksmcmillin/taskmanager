"""Add ai_summary column to articles table

Revision ID: 0030_add_ai_summary_to_articles
Revises: 0029_add_wiki_notifications
Create Date: 2026-03-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030_add_ai_summary_to_articles"
down_revision: str | None = "0029_add_wiki_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("ai_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "ai_summary")
