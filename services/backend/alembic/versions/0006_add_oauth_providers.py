"""Add user_oauth_providers table for social login.

This migration adds:
1. user_oauth_providers table for linking OAuth providers (GitHub, Google, etc.)
2. Indexes on user_id and provider for efficient queries
3. Unique constraints to prevent duplicate provider connections

Revision ID: 0006_add_oauth_providers
Revises: 0005_add_attachments
Create Date: 2026-01-30

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_add_oauth_providers"
down_revision: str | None = "0005_add_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_oauth_providers table."""
    op.create_table(
        "user_oauth_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_username", sa.String(255), nullable=True),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("access_token", sa.String(500), nullable=True),
        sa.Column("refresh_token", sa.String(500), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
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
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_user_oauth_providers_user_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_oauth_provider"),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
    )
    op.create_index("ix_user_oauth_providers_user_id", "user_oauth_providers", ["user_id"])
    op.create_index("ix_user_oauth_providers_provider", "user_oauth_providers", ["provider"])


def downgrade() -> None:
    """Drop user_oauth_providers table."""
    op.drop_index("ix_user_oauth_providers_provider", table_name="user_oauth_providers")
    op.drop_index("ix_user_oauth_providers_user_id", table_name="user_oauth_providers")
    op.drop_table("user_oauth_providers")
