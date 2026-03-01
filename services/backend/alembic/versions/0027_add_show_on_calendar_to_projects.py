"""add show_on_calendar to projects

Revision ID: 0027_add_show_on_calendar_to_projects
Revises: 0026_add_snippets
Create Date: 2026-03-01 00:00:00.000000

Adds show_on_calendar boolean column to projects table.
Projects with show_on_calendar=false are hidden from calendar
and home dashboard views.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0027_add_show_on_calendar_to_projects"
down_revision = "0026_add_snippets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "show_on_calendar",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "show_on_calendar")
