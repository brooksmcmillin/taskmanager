import { TodoDB } from '../../../lib/db.js';
import { config } from '../../../lib/config.js';
import {
  getCorsHeaders,
  corsPreflightResponse,
  oauthErrors,
} from '../../../lib/apiResponse.js';
import crypto from 'crypto';

export async function OPTIONS({ request }) {
  return corsPreflightResponse(request);
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
      return oauthErrors.invalidClient('Invalid client credentials');
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
      return oauthErrors.unsupportedGrantType('Grant type not supported');
    }
  } catch (error) {
    console.error('[OAuth/Token] Error:', error.message);
    console.error('[OAuth/Token] Stack:', error.stack);
    return oauthErrors.serverError('Internal server error');
  }
}

async function handleAuthorizationCodeGrant(formData, client) {
  const code = formData.get('code');
  const redirectUri = formData.get('redirect_uri');
  const codeVerifier = formData.get('code_verifier');

  if (!code || !redirectUri) {
    return oauthErrors.invalidRequest('Missing required parameters');
  }

  // Consume authorization code
  const authCode = await TodoDB.consumeAuthorizationCode(
    code,
    client.client_id
  );
  if (!authCode) {
    return oauthErrors.invalidGrant('Invalid or expired authorization code');
  }

  // Validate redirect URI matches
  if (authCode.redirect_uri !== redirectUri) {
    return oauthErrors.invalidGrant('Redirect URI mismatch');
  }

  // Validate PKCE if used
  if (authCode.code_challenge) {
    if (!codeVerifier) {
      return oauthErrors.invalidRequest('Code verifier required for PKCE');
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
      return oauthErrors.invalidRequest('Unsupported code challenge method');
    }

    if (derivedChallenge !== authCode.code_challenge) {
      return oauthErrors.invalidGrant('Code verifier validation failed');
    }
  }

  // Create access token
  const scopes = JSON.parse(authCode.scopes);
  const expiresIn = config.oauth.accessTokenExpirySeconds;
  const tokenData = await TodoDB.createAccessToken(
    authCode.user_id,
    client.client_id,
    scopes,
    expiresIn
  );

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: expiresIn,
      refresh_token: tokenData.refresh_token,
      scope: scopes.join(' '),
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}

async function handleRefreshTokenGrant(formData, client) {
  const refreshToken = formData.get('refresh_token');

  if (!refreshToken) {
    return oauthErrors.invalidRequest('Missing refresh token');
  }

  // Refresh the access token
  const tokenData = await TodoDB.refreshAccessToken(
    refreshToken,
    client.client_id
  );
  if (!tokenData) {
    return oauthErrors.invalidGrant('Invalid refresh token');
  }

  const expiresIn = config.oauth.accessTokenExpirySeconds;

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: expiresIn,
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
    return oauthErrors.unauthorizedClient(
      'Client is not authorized to use this grant type'
    );
  }

  // Check that client has an owner (user_id)
  if (!client.user_id) {
    return oauthErrors.serverError(
      'Client configuration error: no owner assigned'
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
      return oauthErrors.invalidScope(
        `Invalid scope(s): ${invalidScopes.join(', ')}`
      );
    }
    scopes = requestedScopes;
  } else {
    // Use client's default scopes
    scopes = JSON.parse(client.scopes || '["read"]');
  }

  // Create access token using client's owner as the user context
  const expiresIn = config.oauth.accessTokenExpirySeconds;
  const tokenData = await TodoDB.createAccessToken(
    client.user_id,
    client.client_id,
    scopes,
    expiresIn
  );

  return new Response(
    JSON.stringify({
      access_token: tokenData.token,
      token_type: 'Bearer',
      expires_in: expiresIn,
      scope: scopes.join(' '),
      // Note: refresh_token is intentionally omitted for client_credentials
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
}

/**
 * Handle OAuth 2.0 Device Authorization Grant (RFC 8628)
 */
async function handleDeviceCodeGrant(formData, client) {
  const deviceCode = formData.get('device_code');

  if (!deviceCode) {
    return oauthErrors.invalidRequest('device_code is required');
  }

  // Validate that this client is allowed to use device_code grant
  const allowedGrantTypes = JSON.parse(client.grant_types || '[]');
  if (!allowedGrantTypes.includes('device_code')) {
    return oauthErrors.unauthorizedClient(
      'Client is not authorized to use device flow'
    );
  }

  // Get device authorization status
  const deviceAuth = await TodoDB.getDeviceAuthorizationByDeviceCode(
    deviceCode,
    client.client_id
  );

  if (!deviceAuth) {
    return oauthErrors.invalidGrant('Invalid device code');
  }

  // Check for rate limiting (slow_down)
  if (deviceAuth.slow_down) {
    return oauthErrors.slowDown('Polling too frequently. Please wait longer.');
  }

  // Check if expired
  if (new Date(deviceAuth.expires_at) <= new Date()) {
    return oauthErrors.expiredToken('Device code has expired');
  }

  // Check authorization status
  if (deviceAuth.status === 'denied') {
    return oauthErrors.accessDenied('User denied authorization');
  }

  if (deviceAuth.status === 'pending') {
    return oauthErrors.authorizationPending(
      'User has not yet authorized the device'
    );
  }

  if (deviceAuth.status === 'authorized') {
    // Consume the device code (mark as used)
    const consumedAuth =
      await TodoDB.consumeDeviceAuthorizationCode(deviceCode);

    if (!consumedAuth) {
      return oauthErrors.invalidGrant('Device code already used or expired');
    }

    // Create access token
    const scopes = JSON.parse(consumedAuth.scopes);
    const expiresIn = config.oauth.accessTokenExpirySeconds;
    const tokenData = await TodoDB.createAccessToken(
      consumedAuth.user_id,
      client.client_id,
      scopes,
      expiresIn
    );

    return new Response(
      JSON.stringify({
        access_token: tokenData.token,
        token_type: 'Bearer',
        expires_in: expiresIn,
        refresh_token: tokenData.refresh_token,
        scope: scopes.join(' '),
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store',
        },
      }
    );
  }

  // Unexpected status
  return oauthErrors.serverError('Unexpected authorization status');
}
