-- Initial schema for Todo Manager
-- Created: 2025-06-22

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Projects table
CREATE TABLE projects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) UNIQUE NOT NULL,
  description TEXT,
  color VARCHAR(7) DEFAULT '#3b82f6',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  is_active BOOLEAN DEFAULT true
);

-- Todos table
CREATE TABLE todos (
  id SERIAL PRIMARY KEY,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  title VARCHAR(500) NOT NULL,
  description TEXT,
  priority VARCHAR(20) CHECK(priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
  estimated_hours DECIMAL(5,2) DEFAULT 1.0,
  actual_hours DECIMAL(5,2),
  status VARCHAR(20) CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
  due_date DATE,
  completed_date TIMESTAMP,
  tags JSONB DEFAULT '[]',
  context VARCHAR(50) DEFAULT 'work',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_todos_project ON todos(project_id);
CREATE INDEX idx_todos_status ON todos(status);
CREATE INDEX idx_todos_priority ON todos(priority);
CREATE INDEX idx_todos_due_date ON todos(due_date);
CREATE INDEX idx_todos_tags ON todos USING GIN(tags);

-- Full-text search
CREATE INDEX idx_todos_search ON todos USING GIN(
  to_tsvector('english', title || ' ' || COALESCE(description, ''))
);

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables
CREATE TRIGGER update_projects_updated_at 
  BEFORE UPDATE ON projects 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_todos_updated_at 
  BEFORE UPDATE ON todos 
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
