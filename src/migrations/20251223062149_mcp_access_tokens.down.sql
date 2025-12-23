-- Migration: mcp_access_tokens (rollback)
-- Created: 2025-12-23

DROP INDEX IF EXISTS idx_mcp_access_tokens_expires_at;
DROP INDEX IF EXISTS idx_mcp_access_tokens_token;
DROP TABLE IF EXISTS mcp_access_tokens;
