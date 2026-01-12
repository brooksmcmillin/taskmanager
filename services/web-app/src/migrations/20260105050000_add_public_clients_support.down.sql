-- Migration: add_public_clients_support (rollback)
-- Created: 2026-01-05

-- Remove is_public column
ALTER TABLE oauth_clients
DROP COLUMN IF EXISTS is_public;

-- Restore NOT NULL constraint on client_secret_hash
-- Note: This will fail if any rows have NULL client_secret_hash
-- You may need to delete or update those rows first
ALTER TABLE oauth_clients
ALTER COLUMN client_secret_hash SET NOT NULL;
