-- Migration: device_authorization_codes
-- Created: 2026-01-05
-- OAuth 2.0 Device Authorization Grant (RFC 8628)

-- Create device authorization codes table
CREATE TABLE IF NOT EXISTS device_authorization_codes (
  id SERIAL PRIMARY KEY,
  device_code VARCHAR(255) UNIQUE NOT NULL,      -- Secret code for polling (64 hex chars)
  user_code VARCHAR(16) UNIQUE NOT NULL,          -- Short user-friendly code (e.g., WDJB-MJHT)
  client_id VARCHAR(255) NOT NULL REFERENCES oauth_clients(client_id),
  scopes TEXT NOT NULL,                           -- JSON array of requested scopes
  user_id INTEGER REFERENCES users(id),           -- NULL until user authorizes
  status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, authorized, denied, expired
  expires_at TIMESTAMP NOT NULL,                  -- Typically 15-30 minutes
  interval INTEGER NOT NULL DEFAULT 5,            -- Minimum polling interval in seconds
  last_poll_at TIMESTAMP,                         -- For rate limiting
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_device_auth_codes_device_code ON device_authorization_codes(device_code);
CREATE INDEX IF NOT EXISTS idx_device_auth_codes_user_code ON device_authorization_codes(user_code);
CREATE INDEX IF NOT EXISTS idx_device_auth_codes_status ON device_authorization_codes(status);
CREATE INDEX IF NOT EXISTS idx_device_auth_codes_expires_at ON device_authorization_codes(expires_at);
