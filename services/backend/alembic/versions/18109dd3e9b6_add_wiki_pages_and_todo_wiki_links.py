"""add wiki pages and todo wiki links

Revision ID: 18109dd3e9b6
Revises: 0022_add_mcp_token_tables
Create Date: 2026-02-26 08:54:30.301855

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "18109dd3e9b6"
down_revision: Union[str, None] = "0022_add_mcp_token_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("slug", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "slug", name="uq_wiki_page_user_slug"),
    )
    op.create_index(op.f("ix_wiki_pages_slug"), "wiki_pages", ["slug"], unique=False)
    op.create_table(
        "todo_wiki_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("todo_id", sa.Integer(), nullable=False),
        sa.Column("wiki_page_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["todo_id"], ["todos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["wiki_page_id"], ["wiki_pages.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("todo_id", "wiki_page_id", name="uq_todo_wiki_link"),
    )


def downgrade() -> None:
    op.drop_table("todo_wiki_links")
    op.drop_index(op.f("ix_wiki_pages_slug"), table_name="wiki_pages")
    op.drop_table("wiki_pages")
