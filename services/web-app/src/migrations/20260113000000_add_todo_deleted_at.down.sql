-- Migration: add_todo_deleted_at (rollback)

DROP INDEX IF EXISTS idx_todos_deleted_at;
ALTER TABLE todos DROP COLUMN IF EXISTS deleted_at;
