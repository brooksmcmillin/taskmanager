"""Fix access_tokens schema for FastAPI.

This migration updates the access_tokens table to support:
- Client credentials grants (user_id nullable)
- Optional refresh tokens (refresh_token nullable)
- Refresh token expiration tracking

Revision ID: 0002_fix_access_tokens
Revises: 0001_initial_schema
Create Date: 2026-01-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_fix_access_tokens"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update access_tokens schema."""
    # Add refresh_token_expires_at column
    op.add_column(
        "access_tokens",
        sa.Column(
            "refresh_token_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )

    # Make user_id nullable (for client credentials grants)
    op.alter_column("access_tokens", "user_id", nullable=True)

    # Make refresh_token nullable (for client credentials grants)
    op.alter_column("access_tokens", "refresh_token", nullable=True)


def downgrade() -> None:
    """Revert access_tokens schema changes."""
    op.alter_column("access_tokens", "refresh_token", nullable=False)
    op.alter_column("access_tokens", "user_id", nullable=False)
    op.drop_column("access_tokens", "refresh_token_expires_at")
