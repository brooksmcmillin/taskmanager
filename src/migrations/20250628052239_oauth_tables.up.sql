-- Migration: oauth_tables
-- Created: 2025-06-28T05:22:39.773Z
-- Initialize OAuth database schema
-- This assumes the main TaskManager database schema already exists

-- Create OAuth clients table
CREATE TABLE IF NOT EXISTS oauth_clients (
  id SERIAL PRIMARY KEY,
  client_id VARCHAR(255) UNIQUE NOT NULL,
  client_secret_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  redirect_uris TEXT NOT NULL,
  grant_types TEXT NOT NULL DEFAULT '["authorization_code"]',
  scopes TEXT NOT NULL DEFAULT '["read"]',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create authorization codes table
CREATE TABLE IF NOT EXISTS authorization_codes (
  id SERIAL PRIMARY KEY,
  code VARCHAR(255) UNIQUE NOT NULL,
  client_id VARCHAR(255) NOT NULL REFERENCES oauth_clients(client_id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  redirect_uri VARCHAR(500) NOT NULL,
  scopes TEXT NOT NULL,
  code_challenge VARCHAR(255),
  code_challenge_method VARCHAR(10),
  expires_at TIMESTAMP NOT NULL,
  used BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create access tokens table
CREATE TABLE IF NOT EXISTS access_tokens (
  id SERIAL PRIMARY KEY,
  token VARCHAR(255) UNIQUE NOT NULL,
  refresh_token VARCHAR(255) UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  client_id VARCHAR(255) NOT NULL REFERENCES oauth_clients(client_id),
  scopes TEXT NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_oauth_clients_client_id ON oauth_clients(client_id);
CREATE INDEX IF NOT EXISTS idx_authorization_codes_code ON authorization_codes(code);
CREATE INDEX IF NOT EXISTS idx_access_tokens_token ON access_tokens(token);
CREATE INDEX IF NOT EXISTS idx_access_tokens_refresh_token ON access_tokens(refresh_token);

