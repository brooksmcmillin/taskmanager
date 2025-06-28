-- Rollback for: oauth_tables
-- Created: 2025-06-28T05:22:39.773Z
-- Remove OAuth database schema

-- Drop indexes first
DROP INDEX IF EXISTS idx_oauth_clients_client_id;
DROP INDEX IF EXISTS idx_authorization_codes_code;
DROP INDEX IF EXISTS idx_access_tokens_token;
DROP INDEX IF EXISTS idx_access_tokens_refresh_token;

-- Drop tables in reverse order due to foreign key constraints
DROP TABLE IF EXISTS access_tokens;
DROP TABLE IF EXISTS authorization_codes;
DROP TABLE IF EXISTS oauth_clients;
