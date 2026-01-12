-- Migration: add_user_id_to_oauth_clients (rollback)
-- Created: 2025-10-29

-- Drop index
DROP INDEX IF EXISTS idx_oauth_clients_user_id;

-- Remove user_id column
ALTER TABLE oauth_clients
DROP COLUMN IF EXISTS user_id;
