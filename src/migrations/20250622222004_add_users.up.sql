-- Migration: add_users
-- Created: 2025-06-22T22:20:04.256Z

  CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
  );

  CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
  );

  ALTER TABLE projects
  ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

  ALTER TABLE todos
  ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL;

  CREATE INDEX idx_sessions_user ON sessions(user_id);
  CREATE INDEX idx_sessions_expires ON sessions(expires_at);
  CREATE INDEX idx_projects_user ON projects(user_id);
  CREATE INDEX idx_todos_user ON todos(user_id);

  CREATE TRIGGER update_users_updated_at 
  BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

  CREATE TRIGGER update_sessions_updated_at 
  BEFORE UPDATE ON sessions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
  
