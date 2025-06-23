-- src/migrations/20250622140000_initial_schema.down.sql - Initial rollback
-- Rollback for: initial_schema
-- Created: 2025-06-22

-- Drop triggers
DROP TRIGGER IF EXISTS update_todos_updated_at ON todos;
DROP TRIGGER IF EXISTS update_projects_updated_at ON projects;

-- Drop function
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop indexes
DROP INDEX IF EXISTS idx_todos_search;
DROP INDEX IF EXISTS idx_todos_tags;
DROP INDEX IF EXISTS idx_todos_due_date;
DROP INDEX IF EXISTS idx_todos_priority;
DROP INDEX IF EXISTS idx_todos_status;
DROP INDEX IF EXISTS idx_todos_project;

-- Drop tables (order matters due to foreign keys)
DROP TABLE IF EXISTS todos;
DROP TABLE IF EXISTS projects;

-- src/migrations/20250622141000_add_llm_fields.up.sql - Example future migration
-- Migration: add_llm_fields
-- Created: 2025-06-22

-- Add LLM-related columns to todos
ALTER TABLE todos ADD COLUMN llm_priority_score INTEGER;
ALTER TABLE todos ADD COLUMN llm_priority_reasoning TEXT;
ALTER TABLE todos ADD COLUMN llm_last_analyzed TIMESTAMP;

-- Add index for LLM priority queries
CREATE INDEX idx_todos_llm_priority ON todos(llm_priority_score DESC);

-- Add LLM settings to projects
ALTER TABLE projects ADD COLUMN llm_context_prompt TEXT;
ALTER TABLE projects ADD COLUMN auto_prioritize BOOLEAN DEFAULT false;

-- src/migrations/20250622141000_add_llm_fields.down.sql - Rollback example
-- Rollback for: add_llm_fields
-- Created: 2025-06-22

-- Remove LLM settings from projects
ALTER TABLE projects DROP COLUMN IF EXISTS auto_prioritize;
ALTER TABLE projects DROP COLUMN IF EXISTS llm_context_prompt;

-- Remove index
DROP INDEX IF EXISTS idx_todos_llm_priority;

-- Remove LLM columns from todos
ALTER TABLE todos DROP COLUMN IF EXISTS llm_last_analyzed;
ALTER TABLE todos DROP COLUMN IF EXISTS llm_priority_reasoning;
ALTER TABLE todos DROP COLUMN IF EXISTS llm_priority_score;

