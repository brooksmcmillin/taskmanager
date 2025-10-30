-- Migration: add_user_id_to_oauth_clients
-- Created: 2025-10-29
-- Add user_id to oauth_clients table for ownership tracking

-- Add user_id column (nullable initially to allow existing clients)
ALTER TABLE oauth_clients
ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_oauth_clients_user_id ON oauth_clients(user_id);

-- Optional: Set a default user_id for existing clients (uncomment and set user_id if needed)
-- UPDATE oauth_clients SET user_id = 1 WHERE user_id IS NULL;

-- Optional: Make user_id NOT NULL after setting defaults (uncomment if you want to enforce ownership)
-- ALTER TABLE oauth_clients ALTER COLUMN user_id SET NOT NULL;
