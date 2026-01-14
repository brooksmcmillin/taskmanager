-- Migration: mcp_refresh_tokens (rollback)
-- Created: 2026-01-14

DROP INDEX IF EXISTS idx_mcp_refresh_tokens_expires_at;
DROP INDEX IF EXISTS idx_mcp_refresh_tokens_client_id;
DROP INDEX IF EXISTS idx_mcp_refresh_tokens_token;
DROP TABLE IF EXISTS mcp_refresh_tokens;
