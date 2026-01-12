-- Add client_credentials grant type to existing OAuth clients
-- This enables service-to-service authentication using OAuth2 Client Credentials flow

-- Update all active clients that support authorization_code to also support client_credentials
-- This is a safe update as it only adds capability, doesn't remove any
UPDATE oauth_clients
SET grant_types =
  CASE
    WHEN grant_types::jsonb ? 'client_credentials' THEN grant_types
    ELSE (grant_types::jsonb || '["client_credentials"]'::jsonb)::text
  END
WHERE is_active = true
  AND grant_types::jsonb ? 'authorization_code';
