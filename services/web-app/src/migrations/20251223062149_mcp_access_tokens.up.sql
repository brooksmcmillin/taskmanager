-- Migration: mcp_access_tokens
-- Created: 2025-12-23
-- Add table for MCP (Model Context Protocol) access tokens
-- These tokens are issued by the MCP auth server after TaskManager OAuth authentication

CREATE TABLE IF NOT EXISTS mcp_access_tokens (
  id SERIAL PRIMARY KEY,
  token VARCHAR(255) UNIQUE NOT NULL,
  client_id VARCHAR(255) NOT NULL,
  scopes TEXT NOT NULL,
  resource VARCHAR(500),  -- RFC 8707 resource binding (audience)
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for fast token lookups during introspection
CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_token ON mcp_access_tokens(token);

-- Create index for cleanup of expired tokens
CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_expires_at ON mcp_access_tokens(expires_at);
