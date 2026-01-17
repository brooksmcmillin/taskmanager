"""Fix access_tokens schema for FastAPI.

This migration makes refresh_token nullable to support client credentials grants
where no refresh token is issued.

Note: user_id and refresh_token_expires_at are already nullable in the initial schema.

Revision ID: 0002_fix_access_tokens
Revises: 0001_initial_schema
Create Date: 2026-01-16

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_fix_access_tokens"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Update access_tokens schema."""
    # Make refresh_token nullable (for client credentials grants)
    # Note: refresh_token_expires_at and user_id are already nullable in initial schema
    op.alter_column("access_tokens", "refresh_token", nullable=True)


def downgrade() -> None:
    """Revert access_tokens schema changes."""
    op.alter_column("access_tokens", "refresh_token", nullable=False)
