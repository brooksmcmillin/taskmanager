-- Migration: recurring_tasks
-- Created: 2026-01-11
-- Adds support for recurring/repeating tasks

-- Recurring tasks table (templates for generating todos)
CREATE TABLE recurring_tasks (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,

  -- Recurrence pattern
  frequency VARCHAR(20) NOT NULL CHECK(frequency IN ('daily', 'weekly', 'monthly', 'yearly')),
  interval_value INTEGER DEFAULT 1 CHECK(interval_value >= 1),
  weekdays INTEGER[] DEFAULT NULL, -- For weekly: days of week (0=Sunday, 1=Monday, ..., 6=Saturday)
  day_of_month INTEGER DEFAULT NULL CHECK(day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)),

  -- Time bounds
  start_date DATE NOT NULL,
  end_date DATE DEFAULT NULL, -- NULL = no end date
  next_due_date DATE NOT NULL,

  -- Task template fields (copied to generated todos)
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  priority VARCHAR(20) CHECK(priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
  estimated_hours DECIMAL(5,2) DEFAULT 1.0,
  tags JSONB DEFAULT '[]',
  context VARCHAR(50) DEFAULT 'work',

  -- Behavior control
  skip_missed BOOLEAN DEFAULT true, -- true = floating (next from today), false = fixed schedule
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Link generated todos back to their recurring template
ALTER TABLE todos ADD COLUMN recurring_task_id INTEGER REFERENCES recurring_tasks(id) ON DELETE SET NULL;

-- Indexes for performance
CREATE INDEX idx_recurring_tasks_user ON recurring_tasks(user_id);
CREATE INDEX idx_recurring_tasks_next_due ON recurring_tasks(next_due_date) WHERE is_active = true;
CREATE INDEX idx_recurring_tasks_active ON recurring_tasks(user_id, is_active) WHERE is_active = true;
CREATE INDEX idx_todos_recurring ON todos(recurring_task_id) WHERE recurring_task_id IS NOT NULL;

-- Apply update trigger
CREATE TRIGGER update_recurring_tasks_updated_at
  BEFORE UPDATE ON recurring_tasks
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
