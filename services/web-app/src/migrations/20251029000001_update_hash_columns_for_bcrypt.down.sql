-- Migration: update_hash_columns_for_bcrypt (rollback)
-- Created: 2025-10-29

-- Revert api_keys.key_hash to original size
-- WARNING: This will fail if any bcrypt hashes exist (which are 60+ chars)
ALTER TABLE api_keys
ALTER COLUMN key_hash TYPE VARCHAR(64);
