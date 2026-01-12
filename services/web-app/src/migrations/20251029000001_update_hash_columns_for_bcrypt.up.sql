-- Migration: update_hash_columns_for_bcrypt
-- Created: 2025-10-29
-- Update hash columns to accommodate bcrypt hashes (60 chars, but use 72 for safety)

-- Update api_keys.key_hash to support bcrypt hashes
ALTER TABLE api_keys
ALTER COLUMN key_hash TYPE VARCHAR(72);

-- oauth_clients.client_secret_hash is already VARCHAR(255), which is sufficient
-- No changes needed for oauth_clients

-- Note: This migration should be run BEFORE creating new API keys or OAuth clients with bcrypt
-- Any existing SHA256 hashes (64 chars) will still fit in the new column size
