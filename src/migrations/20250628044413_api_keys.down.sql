-- Rollback for: api_keys
-- Created: 2025-06-28T04:44:13.331Z
    DROP INDEX IF EXISTS idx_api_keys_hash;
    DROP INDEX IF EXISTS idx_api_keys_user_active;

    DROP TABLE IF EXISTS api_keys;
