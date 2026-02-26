"""Add MCP access and refresh token tables.

Replaces legacy mcp_access_tokens and mcp_refresh_tokens tables with
updated schema including user_id FK, timezone-aware timestamps, and
proper indexes. The legacy tables were created by SQL migrations that
predated the alembic migration chain.

Revision ID: 0022_add_mcp_token_tables
Revises: 0021_add_deadline_type
Create Date: 2026-02-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_add_mcp_token_tables"
down_revision: str | None = "0021_add_deadline_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(connection: sa.Connection, table_name: str) -> bool:
    result = connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :name)"
        ),
        {"name": table_name},
    )
    return result.scalar()


def upgrade() -> None:
    """Replace legacy MCP token tables with updated schema."""
    conn = op.get_bind()

    # Drop legacy tables if they exist (ephemeral token data, safe to drop)
    if _table_exists(conn, "mcp_refresh_tokens"):
        op.drop_table("mcp_refresh_tokens")
    if _table_exists(conn, "mcp_access_tokens"):
        op.drop_table("mcp_access_tokens")

    op.create_table(
        "mcp_access_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(255), unique=True, nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scopes", sa.Text, nullable=False),
        sa.Column("resource", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_mcp_access_tokens_client_id", "mcp_access_tokens", ["client_id"]
    )
    op.create_index(
        "ix_mcp_access_tokens_expires_at", "mcp_access_tokens", ["expires_at"]
    )
    op.create_index("ix_mcp_access_tokens_user_id", "mcp_access_tokens", ["user_id"])

    op.create_table(
        "mcp_refresh_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(255), unique=True, nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scopes", sa.Text, nullable=True),
        sa.Column("resource", sa.String(500), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_mcp_refresh_tokens_client_id", "mcp_refresh_tokens", ["client_id"]
    )
    op.create_index(
        "ix_mcp_refresh_tokens_expires_at", "mcp_refresh_tokens", ["expires_at"]
    )
    op.create_index("ix_mcp_refresh_tokens_user_id", "mcp_refresh_tokens", ["user_id"])


def downgrade() -> None:
    """Remove MCP token tables."""
    op.drop_index("ix_mcp_refresh_tokens_user_id", table_name="mcp_refresh_tokens")
    op.drop_index("ix_mcp_refresh_tokens_expires_at", table_name="mcp_refresh_tokens")
    op.drop_index("ix_mcp_refresh_tokens_client_id", table_name="mcp_refresh_tokens")
    op.drop_table("mcp_refresh_tokens")

    op.drop_index("ix_mcp_access_tokens_user_id", table_name="mcp_access_tokens")
    op.drop_index("ix_mcp_access_tokens_expires_at", table_name="mcp_access_tokens")
    op.drop_index("ix_mcp_access_tokens_client_id", table_name="mcp_access_tokens")
    op.drop_table("mcp_access_tokens")
