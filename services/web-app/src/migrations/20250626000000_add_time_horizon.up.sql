-- Add time_horizon field to todos table
-- Created: 2025-06-26

ALTER TABLE todos ADD COLUMN time_horizon VARCHAR(20) 
CHECK(time_horizon IN ('today', 'this_week', 'next_week', 'this_month', 'next_month', 'this_quarter', 'next_quarter', 'this_year', 'next_year', 'someday')) 
DEFAULT NULL;

-- Add index for time_horizon filtering
CREATE INDEX idx_todos_time_horizon ON todos(time_horizon);