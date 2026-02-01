"""Add agent integration fields to todos table.

This migration adds fields to support AI agent task processing:
1. agent_actionable - Whether an agent can complete this task without human intervention
2. action_type - Type of action required (research, code, email, etc.)
3. agent_status - Agent's processing status for the task
4. agent_notes - Agent-generated context and research notes
5. blocking_reason - Why the agent cannot proceed (if blocked)

Revision ID: 0007_add_agent_fields
Revises: 0006_add_position_and_archived_at
Create Date: 2026-01-31

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_add_agent_fields"
down_revision: str | None = "0006_add_position_and_archived_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add agent integration fields to todos table."""
    # agent_actionable - nullable boolean, None means unclassified
    op.add_column(
        "todos",
        sa.Column("agent_actionable", sa.Boolean(), nullable=True),
    )

    # action_type - enum for type of action required
    op.add_column(
        "todos",
        sa.Column("action_type", sa.String(20), nullable=True),
    )

    # agent_status - enum for agent's processing status
    op.add_column(
        "todos",
        sa.Column("agent_status", sa.String(20), nullable=True),
    )

    # agent_notes - text field for agent-generated context
    op.add_column(
        "todos",
        sa.Column("agent_notes", sa.Text(), nullable=True),
    )

    # blocking_reason - why agent can't proceed
    op.add_column(
        "todos",
        sa.Column("blocking_reason", sa.String(500), nullable=True),
    )

    # Create index on agent_actionable for efficient filtering
    op.create_index("ix_todos_agent_actionable", "todos", ["agent_actionable"])

    # Create index on action_type for filtering by action type
    op.create_index("ix_todos_action_type", "todos", ["action_type"])

    # Create index on agent_status for filtering agent work queue
    op.create_index("ix_todos_agent_status", "todos", ["agent_status"])


def downgrade() -> None:
    """Remove agent integration fields from todos table."""
    op.drop_index("ix_todos_agent_status", table_name="todos")
    op.drop_index("ix_todos_action_type", table_name="todos")
    op.drop_index("ix_todos_agent_actionable", table_name="todos")
    op.drop_column("todos", "blocking_reason")
    op.drop_column("todos", "agent_notes")
    op.drop_column("todos", "agent_status")
    op.drop_column("todos", "action_type")
    op.drop_column("todos", "agent_actionable")
