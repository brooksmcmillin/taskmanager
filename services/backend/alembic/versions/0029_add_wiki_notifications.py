"""Add wiki page subscriptions and notifications tables

Revision ID: 0029_add_wiki_notifications
Revises: 0028_add_bookmarks
Create Date: 2026-03-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029_add_wiki_notifications"
down_revision: str | None = "0028_add_bookmarks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create notification_type_enum
    notification_type_enum = sa.Enum(
        "wiki_page_updated",
        "wiki_page_created",
        "wiki_page_deleted",
        name="notification_type_enum",
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    # Create wiki_page_subscriptions table
    op.create_table(
        "wiki_page_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wiki_page_id",
            sa.Integer(),
            sa.ForeignKey("wiki_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "include_children",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "wiki_page_id", name="uq_wiki_subscription_user_page"
        ),
    )
    op.create_index(
        "ix_wiki_page_subscriptions_user_id",
        "wiki_page_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_wiki_page_subscriptions_wiki_page_id",
        "wiki_page_subscriptions",
        ["wiki_page_id"],
    )

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notification_type",
            notification_type_enum,
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "wiki_page_id",
            sa.Integer(),
            sa.ForeignKey("wiki_pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notifications_user_id",
        "notifications",
        ["user_id"],
    )
    op.create_index(
        "ix_notifications_is_read",
        "notifications",
        ["is_read"],
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("wiki_page_subscriptions")
    sa.Enum(name="notification_type_enum").drop(op.get_bind(), checkfirst=True)
