"""add snippets table

Revision ID: 0026_add_snippets
Revises: 0025_add_wiki_parent_id_and_tags
Create Date: 2026-02-28 00:00:00.000000

Adds snippets table for storing small, dated log entries
like maintenance records, measurements, and quick notes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_add_snippets"
down_revision: str | None = "0025_add_wiki_parent_id_and_tags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "snippets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "snippet_date",
            sa.Date(),
            server_default=sa.func.current_date(),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
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
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index("ix_snippets_user_id", "snippets", ["user_id"])
    op.create_index("ix_snippets_category", "snippets", ["category"])
    op.create_index("ix_snippets_snippet_date", "snippets", ["snippet_date"])


def downgrade() -> None:
    op.drop_index("ix_snippets_snippet_date", table_name="snippets")
    op.drop_index("ix_snippets_category", table_name="snippets")
    op.drop_index("ix_snippets_user_id", table_name="snippets")
    op.drop_table("snippets")
