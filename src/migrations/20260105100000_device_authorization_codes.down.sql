-- Migration: device_authorization_codes (rollback)
-- Created: 2026-01-05

DROP INDEX IF EXISTS idx_device_auth_codes_expires_at;
DROP INDEX IF EXISTS idx_device_auth_codes_status;
DROP INDEX IF EXISTS idx_device_auth_codes_user_code;
DROP INDEX IF EXISTS idx_device_auth_codes_device_code;
DROP TABLE IF EXISTS device_authorization_codes;
