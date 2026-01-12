-- Remove client_credentials grant type from OAuth clients
-- Reverses the addition of client_credentials grant type

UPDATE oauth_clients
SET grant_types = (grant_types::jsonb - 'client_credentials')::text
WHERE grant_types::jsonb ? 'client_credentials';
