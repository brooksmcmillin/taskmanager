"""add wiki revisions and soft delete

Revision ID: 0023_wiki_revisions
Revises: 18109dd3e9b6
Create Date: 2026-02-26 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0023_wiki_revisions"
down_revision: Union[str, None] = "18109dd3e9b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add soft delete and revision tracking to wiki_pages
    op.add_column(
        "wiki_pages",
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "wiki_pages",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create wiki_page_revisions table
    op.create_table(
        "wiki_page_revisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wiki_page_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["wiki_page_id"], ["wiki_pages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("wiki_page_revisions")
    op.drop_column("wiki_pages", "deleted_at")
    op.drop_column("wiki_pages", "revision_number")
