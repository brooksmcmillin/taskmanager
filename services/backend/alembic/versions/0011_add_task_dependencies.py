"""Add task_dependencies table for task dependency relationships.

This migration creates a many-to-many relationship between tasks,
allowing tasks to depend on other tasks that must be completed first.

Revision ID: 0011_add_task_dependencies
Revises: 0010_add_autonomy_tier
Create Date: 2026-02-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_add_task_dependencies"
down_revision: str | None = "0010_add_autonomy_tier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create task_dependencies join table."""
    op.create_table(
        "task_dependencies",
        sa.Column("dependent_id", sa.Integer(), nullable=False),
        sa.Column("dependency_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["dependent_id"],
            ["todos.id"],
            name="fk_task_dependencies_dependent_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dependency_id"],
            ["todos.id"],
            name="fk_task_dependencies_dependency_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dependent_id", "dependency_id"),
        sa.CheckConstraint(
            "dependent_id != dependency_id",
            name="ck_task_dependencies_no_self_reference",
        ),
    )

    # Create indexes for efficient lookups
    op.create_index(
        "ix_task_dependencies_dependent_id",
        "task_dependencies",
        ["dependent_id"],
    )
    op.create_index(
        "ix_task_dependencies_dependency_id",
        "task_dependencies",
        ["dependency_id"],
    )
    # Composite index for optimized "dependents" query (lookup by dependency_id)
    op.create_index(
        "ix_task_dependencies_dependency_dependent",
        "task_dependencies",
        ["dependency_id", "dependent_id"],
    )


def downgrade() -> None:
    """Drop task_dependencies table."""
    op.drop_index(
        "ix_task_dependencies_dependency_dependent", table_name="task_dependencies"
    )
    op.drop_index("ix_task_dependencies_dependency_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_dependent_id", table_name="task_dependencies")
    op.drop_table("task_dependencies")
