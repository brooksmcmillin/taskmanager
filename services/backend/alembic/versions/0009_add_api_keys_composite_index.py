"""Add composite index for API key lookup performance.

This adds a composite index on (key_prefix, is_active) to improve
query performance when validating API keys.

Revision ID: 0009_add_api_keys_composite_index
Revises: 0008_add_api_keys
Create Date: 2026-02-02

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009_add_api_keys_composite_index"
down_revision: str | None = "0008_add_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add composite index for efficient API key lookup."""
    op.create_index(
        "ix_api_keys_prefix_active",
        "api_keys",
        ["key_prefix", "is_active"],
    )


def downgrade() -> None:
    """Remove composite index."""
    op.drop_index("ix_api_keys_prefix_active", table_name="api_keys")
