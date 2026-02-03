"""Add webauthn_credentials table for passkey authentication.

Revision ID: 0012_add_webauthn_credentials
Revises: 0011_add_task_dependencies
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012_add_webauthn_credentials"
down_revision: str | None = "0011_add_task_dependencies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create webauthn_credentials table."""
    op.create_table(
        "webauthn_credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("credential_id", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("transports", sa.String(255), nullable=True),
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    # Create indexes
    op.create_index(
        "ix_webauthn_credentials_user_id", "webauthn_credentials", ["user_id"]
    )
    op.create_index(
        "ix_webauthn_credentials_credential_id",
        "webauthn_credentials",
        ["credential_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop webauthn_credentials table."""
    op.drop_index(
        "ix_webauthn_credentials_credential_id", table_name="webauthn_credentials"
    )
    op.drop_index("ix_webauthn_credentials_user_id", table_name="webauthn_credentials")
    op.drop_table("webauthn_credentials")
