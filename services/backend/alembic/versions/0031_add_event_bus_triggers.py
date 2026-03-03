"""Add event bus triggers for real-time notifications

Revision ID: 0031_add_event_bus_triggers
Revises: 0030_add_ai_summary_to_articles
Create Date: 2026-03-03

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_add_event_bus_triggers"
down_revision: str | None = "0030_add_ai_summary_to_articles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create the PL/pgSQL trigger function.
    # Builds a compact JSON payload:
    #   {"t":"todos","op":"U","id":42,"uid":1,"tab":"a1b2c3d4"}
    # Soft-deletes (deleted_at going from NULL to non-NULL) emit op="D".
    # tab is read from a session-level GUC set by the backend.
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_event() RETURNS trigger AS $$
        DECLARE
            rec   RECORD;
            op_ch TEXT;
            tab   TEXT;
        BEGIN
            -- Pick the record (NEW for I/U, OLD for D)
            IF TG_OP = 'DELETE' THEN
                rec := OLD;
                op_ch := 'D';
            ELSE
                rec := NEW;
                IF TG_OP = 'INSERT' THEN
                    op_ch := 'I';
                ELSE
                    -- Treat soft-deletes as 'D'
                    IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
                        op_ch := 'D';
                    ELSE
                        op_ch := 'U';
                    END IF;
                END IF;
            END IF;

            -- Read the tab id GUC (empty string if unset)
            tab := coalesce(current_setting('app.tab_id', true), '');

            PERFORM pg_notify('events', json_build_object(
                't',   TG_TABLE_NAME,
                'op',  op_ch,
                'id',  rec.id,
                'uid', rec.user_id,
                'tab', tab
            )::text);

            RETURN rec;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # AFTER triggers on the four core tables
    op.execute("""
        CREATE TRIGGER trg_todos_events
        AFTER INSERT OR UPDATE OR DELETE ON todos
        FOR EACH ROW EXECUTE FUNCTION notify_event();
    """)

    op.execute("""
        CREATE TRIGGER trg_projects_events
        AFTER INSERT OR UPDATE OR DELETE ON projects
        FOR EACH ROW EXECUTE FUNCTION notify_event();
    """)

    op.execute("""
        CREATE TRIGGER trg_wiki_pages_events
        AFTER INSERT OR UPDATE OR DELETE ON wiki_pages
        FOR EACH ROW EXECUTE FUNCTION notify_event();
    """)

    # Notifications: INSERT only (no user-facing updates/deletes emit events)
    op.execute("""
        CREATE TRIGGER trg_notifications_events
        AFTER INSERT ON notifications
        FOR EACH ROW EXECUTE FUNCTION notify_event();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_notifications_events ON notifications;")
    op.execute("DROP TRIGGER IF EXISTS trg_wiki_pages_events ON wiki_pages;")
    op.execute("DROP TRIGGER IF EXISTS trg_projects_events ON projects;")
    op.execute("DROP TRIGGER IF EXISTS trg_todos_events ON todos;")
    op.execute("DROP FUNCTION IF EXISTS notify_event();")
