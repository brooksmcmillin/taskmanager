"""Add registration codes and is_admin to users.

This migration adds:
1. is_admin column to users table for admin access control
2. registration_codes table for controlled user registration

Revision ID: 0003_add_registration_codes
Revises: 0002_fix_access_tokens
Create Date: 2026-01-24

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_add_registration_codes"
down_revision: str | None = "0002_fix_access_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add registration codes table and is_admin column."""
    # Add is_admin column to users table
    op.add_column(
        "users",
        sa.Column(
            "is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )

    # Create registration_codes table
    op.create_table(
        "registration_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("current_uses", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        "ix_registration_codes_code", "registration_codes", ["code"], unique=True
    )
    op.create_index(
        "idx_registration_codes_active",
        "registration_codes",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """Remove registration codes table and is_admin column."""
    op.drop_table("registration_codes")
    op.drop_column("users", "is_admin")
