-- Rollback for: add_users
-- Created: 2025-06-22T22:20:04.256Z

  DROP TRIGGER IF EXISTS update_users_updated_at ON users;
  DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;

  DROP INDEX IF EXISTS idx_sessions_user;
  DROP INDEX IF EXISTS idx_sessions_expires;
  DROP INDEX IF EXISTS idx_projects_user;
  DROP INDEX IF EXISTS idx_todos_user;

  ALTER TABLE projects
  DROP COLUMN user_id;

  ALTER TABLE todos
  DROP COLUMN user_id;

  DROP TABLE IF EXISTS sessions;
  DROP TABLE IF EXISTS users;
  
