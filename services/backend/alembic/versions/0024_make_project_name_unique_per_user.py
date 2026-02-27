"""make project name unique per user (case-insensitive)

Revision ID: 0024_project_name_unique_per_user
Revises: 0023_wiki_revisions
Create Date: 2026-02-27 00:00:00.000000

Replaces the global UniqueConstraint("name") on the projects table with a
per-user case-insensitive unique constraint on (user_id, lower(name)).

This fixes silent 500 errors when two different users attempt to create
projects with the same name (or same name, different case) via category
auto-creation in task creation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_project_name_unique_per_user"
down_revision: str | None = "0023_wiki_revisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old global unique constraint on name
    op.drop_constraint("projects_name_key", "projects", type_="unique")

    # Add a per-user case-insensitive unique index using a functional expression.
    # This allows two different users to have projects with the same name,
    # but prevents duplicate names (case-insensitively) within the same user.
    op.create_index(
        "uq_projects_user_lower_name",
        "projects",
        [sa.text("user_id"), sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    # Remove the per-user index
    op.drop_index("uq_projects_user_lower_name", table_name="projects")

    # Restore the global unique constraint (may fail if duplicate names exist
    # across users after the upgrade was applied and used)
    op.create_unique_constraint("projects_name_key", "projects", ["name"])
