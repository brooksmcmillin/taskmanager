-- Remove time_horizon field from todos table
-- Created: 2025-06-26

DROP INDEX IF EXISTS idx_todos_time_horizon;
ALTER TABLE todos DROP COLUMN IF EXISTS time_horizon;