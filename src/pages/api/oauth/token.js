import { TodoDB } from '../../../lib/db.js';
import crypto from 'crypto';

export async function OPTIONS() {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}

export async function POST({ request }) {
  try {
    const formData = await request.formData();
    const grantType = formData.get('grant_type');
    const clientId = formData.get('client_id');
    const clientSecret = formData.get('client_secret');

    // Validate client credentials
    const client = await TodoDB.validateOAuthClient(clientId, clientSecret);
    if (!client) {
      return new Response(
        JSON.stringify({
          error: 'invalid_client',
          error_description: 'Invalid client credentials',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    if (grantType === 'authorization_code') {
      return await handleAuthorizationCodeGrant(formData, client);
    } else if (grantType === 'refresh_token') {
      return await handleRefreshTokenGrant(formData, client);
    } else if (grantType === 'client_credentials') {
      return await handleClientCredentialsGrant(formData, client);
    } else if (grantType === 'urn:ietf:params:oauth:grant-type:device_code') {
      return await handleDeviceCodeGrant(formData, client);
    } else {
      return new Response(
        JSON.stringify({
          error: 'unsupported_grant_type',
          error_description: 'Grant type not supported',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  } catch (error) {
    console.error('[OAuth/Token] Error:', error.message);
    return new Response(
      JSON.stringify({
        error: 'server_error',
        error_description: 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

async function handleAuthorizationCodeGrant(formData, client) {
  const code = formData.get('code');
  const redirectUri = formData.get('redirect_uri');
  const codeVerifier = formData.get('code_verifier');

  if (!code || !redirectUri) {
    return new Response(
      JSON.stringify({
        error: 'invalid_request',
        error_description: 'Missing required parameters',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Consume authorization code
  const authCode = await TodoDB.consumeAuthorizationCode(
    code,
    client.client_id
  );
  if (!authCode) {
    return new Response(
      JSON.stringify({
        error: 'invalid_grant',
        error_description: 'Invalid or expired authorization code',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Validate redirect URI matches
  if (authCode.redirect_uri !== redirectUri) {
    return new Response(
      JSON.stringify({
        error: 'invalid_grant',
        error_description: 'Redirect URI mismatch',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Validate PKCE if used
  if (authCode.code_challenge) {
    if (!codeVerifier) {
      return new Response(
        JSON.stringify({
          error: 'invalid_request',
          error_description: 'Code verifier required for PKCE',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const challengeMethod = authCode.code_challenge_method || 'plain';
    let derivedChallenge;

    if (challengeMethod === 'S256') {
      derivedChallenge = crypto
        .createHash('sha256')
        .update(codeVerifier)
        .digest('base64url');
    } else if (challengeMethod === 'plain') {
      derivedChallenge = codeVerifier;
    } else {
      return new Response(
        JSON.stringify({
          error: 'invalid_request',
          error_description: 'Unsupported code challenge method',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    if (derivedChallenge !== authCode.code_challenge) {
      return new Response(
        JSON.stringify({
          error: 'invalid_grant',
          error_description: 'Code verifier validation failed',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
  }

  // Create access token
  const scopes = JSON.parse(authCode.scopes);
  const tokenData = await TodoDB.createAccessToken(
    authCode.user_id,
    client.client_id,
    scopes,
    3600 // 1 hour expiry
  );

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: 3600,
      refresh_token: tokenData.refresh_token,
      scope: scopes.join(' '),
    }),
    {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    }
  );
}

async function handleRefreshTokenGrant(formData, client) {
  const refreshToken = formData.get('refresh_token');

  if (!refreshToken) {
    return new Response(
      JSON.stringify({
        error: 'invalid_request',
        error_description: 'Missing refresh token',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Refresh the access token
  const tokenData = await TodoDB.refreshAccessToken(
    refreshToken,
    client.client_id
  );
  if (!tokenData) {
    return new Response(
      JSON.stringify({
        error: 'invalid_grant',
        error_description: 'Invalid refresh token',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: 3600,
      refresh_token: tokenData.refresh_token,
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}

async function handleClientCredentialsGrant(formData, client) {
  // Client credentials grant is used for machine-to-machine authentication

  // Validate that this client is allowed to use client_credentials grant
  const allowedGrantTypes = JSON.parse(client.grant_types || '[]');
  if (!allowedGrantTypes.includes('client_credentials')) {
    return new Response(
      JSON.stringify({
        error: 'unauthorized_client',
        error_description: 'Client is not authorized to use this grant type',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Check that client has an owner (user_id)
  if (!client.user_id) {
    return new Response(
      JSON.stringify({
        error: 'server_error',
        error_description: 'Client configuration error: no owner assigned',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Get requested scope (optional) or use client's default scopes
  const requestedScope = formData.get('scope');
  let scopes;

  if (requestedScope) {
    // Validate requested scopes against client's allowed scopes
    const clientScopes = JSON.parse(client.scopes || '["read"]');
    const requestedScopes = requestedScope.split(' ');

    // Check all requested scopes are allowed
    const invalidScopes = requestedScopes.filter(
      (s) => !clientScopes.includes(s)
    );
    if (invalidScopes.length > 0) {
      return new Response(
        JSON.stringify({
          error: 'invalid_scope',
          error_description: `Invalid scope(s): ${invalidScopes.join(', ')}`,
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
    scopes = requestedScopes;
  } else {
    // Use client's default scopes
    scopes = JSON.parse(client.scopes || '["read"]');
  }

  // Create access token using client's owner as the user context
  const tokenData = await TodoDB.createAccessToken(
    client.user_id,
    client.client_id,
    scopes,
    3600 // 1 hour expiry
  );

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: 3600,
      scope: scopes.join(' '),
      // Note: refresh_token is intentionally omitted for client_credentials
    }),
    {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
      },
    }
  );
}

/**
 * Handle OAuth 2.0 Device Authorization Grant (RFC 8628)
 */
async function handleDeviceCodeGrant(formData, client) {
  const deviceCode = formData.get('device_code');

  if (!deviceCode) {
    return new Response(
      JSON.stringify({
        error: 'invalid_request',
        error_description: 'device_code is required',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Validate that this client is allowed to use device_code grant
  const allowedGrantTypes = JSON.parse(client.grant_types || '[]');
  if (!allowedGrantTypes.includes('device_code')) {
    return new Response(
      JSON.stringify({
        error: 'unauthorized_client',
        error_description: 'Client is not authorized to use device flow',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Get device authorization status
  const deviceAuth = await TodoDB.getDeviceAuthorizationByDeviceCode(
    deviceCode,
    client.client_id
  );

  if (!deviceAuth) {
    return new Response(
      JSON.stringify({
        error: 'invalid_grant',
        error_description: 'Invalid device code',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Check for rate limiting (slow_down)
  if (deviceAuth.slow_down) {
    return new Response(
      JSON.stringify({
        error: 'slow_down',
        error_description: 'Polling too frequently. Please wait longer.',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Check if expired
  if (new Date(deviceAuth.expires_at) <= new Date()) {
    return new Response(
      JSON.stringify({
        error: 'expired_token',
        error_description: 'Device code has expired',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // Check authorization status
  if (deviceAuth.status === 'denied') {
    return new Response(
      JSON.stringify({
        error: 'access_denied',
        error_description: 'User denied authorization',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  if (deviceAuth.status === 'pending') {
    return new Response(
      JSON.stringify({
        error: 'authorization_pending',
        error_description: 'User has not yet authorized the device',
      }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  if (deviceAuth.status === 'authorized') {
    // Consume the device code (mark as used)
    const consumedAuth = await TodoDB.consumeDeviceAuthorizationCode(deviceCode);

    if (!consumedAuth) {
      return new Response(
        JSON.stringify({
          error: 'invalid_grant',
          error_description: 'Device code already used or expired',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Create access token
    const scopes = JSON.parse(consumedAuth.scopes);
    const tokenData = await TodoDB.createAccessToken(
      consumedAuth.user_id,
      client.client_id,
      scopes,
      3600 // 1 hour expiry
    );

    return new Response(
      JSON.stringify({
        access_token: tokenData.token,
        token_type: 'Bearer',
        expires_in: 3600,
        refresh_token: tokenData.refresh_token,
        scope: scopes.join(' '),
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      }
    );
  }

  // Unexpected status
  return new Response(
    JSON.stringify({
      error: 'server_error',
      error_description: 'Unexpected authorization status',
    }),
    {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}
