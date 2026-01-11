-- Rollback: recurring_tasks

-- Drop trigger first
DROP TRIGGER IF EXISTS update_recurring_tasks_updated_at ON recurring_tasks;

-- Remove the foreign key column from todos
ALTER TABLE todos DROP COLUMN IF EXISTS recurring_task_id;

-- Drop the recurring_tasks table (cascades indexes)
DROP TABLE IF EXISTS recurring_tasks;
