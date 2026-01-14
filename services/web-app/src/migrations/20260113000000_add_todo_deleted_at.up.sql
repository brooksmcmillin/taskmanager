-- Migration: add_todo_deleted_at
-- Add soft delete support for todos

-- Add deleted_at column (NULL = not deleted, timestamp = when deleted)
ALTER TABLE todos ADD COLUMN deleted_at TIMESTAMP DEFAULT NULL;

-- Index for efficiently querying non-deleted and deleted todos
CREATE INDEX idx_todos_deleted_at ON todos(deleted_at);
