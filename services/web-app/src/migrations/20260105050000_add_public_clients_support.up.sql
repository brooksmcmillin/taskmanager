-- Migration: add_public_clients_support
-- Created: 2026-01-05
-- Add support for public OAuth clients (RFC 6749 Section 2.1)
-- Public clients (native apps, SPAs, devices) don't use client_secret

-- Add is_public column to track public vs confidential clients
ALTER TABLE oauth_clients
ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT false;

-- Make client_secret_hash nullable for public clients
ALTER TABLE oauth_clients
ALTER COLUMN client_secret_hash DROP NOT NULL;

-- Update device flow clients to be public by default (they typically are)
-- Only update clients that have device_code in their grant_types
UPDATE oauth_clients
SET is_public = true
WHERE grant_types::jsonb ? 'device_code'
  AND is_public = false;
