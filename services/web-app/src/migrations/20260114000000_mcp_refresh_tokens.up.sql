-- Migration: mcp_refresh_tokens
-- Created: 2026-01-14
-- Add table for MCP refresh tokens (OAuth 2.0 refresh token support)
-- These tokens enable obtaining new access tokens without re-authentication

CREATE TABLE IF NOT EXISTS mcp_refresh_tokens (
  id SERIAL PRIMARY KEY,
  token VARCHAR(255) UNIQUE NOT NULL,
  client_id VARCHAR(255) NOT NULL,
  scopes TEXT,
  resource VARCHAR(500),  -- RFC 8707 resource binding (audience)
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast token lookups during refresh
CREATE INDEX IF NOT EXISTS idx_mcp_refresh_tokens_token ON mcp_refresh_tokens(token);

-- Create index for client-based queries
CREATE INDEX IF NOT EXISTS idx_mcp_refresh_tokens_client_id ON mcp_refresh_tokens(client_id);

-- Create index for cleanup of expired tokens
CREATE INDEX IF NOT EXISTS idx_mcp_refresh_tokens_expires_at ON mcp_refresh_tokens(expires_at);

COMMENT ON TABLE mcp_refresh_tokens IS 'Stores MCP OAuth 2.0 refresh tokens with 7-day expiration for token renewal without re-authentication';
