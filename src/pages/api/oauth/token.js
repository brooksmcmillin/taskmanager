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
    console.log('[OAuth/Token] POST request received');
    const formData = await request.formData();
    const grantType = formData.get('grant_type');
    const clientId = formData.get('client_id');
    const clientSecret = formData.get('client_secret');

    console.log('[OAuth/Token] Request params:', {
      grant_type: grantType,
      client_id: clientId,
      has_client_secret: !!clientSecret
    });

    // Validate client credentials
    const client = await TodoDB.validateOAuthClient(clientId, clientSecret);
    if (!client) {
      console.log('[OAuth/Token] Client validation failed for client_id:', clientId);
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

    console.log('[OAuth/Token] Client validated:', client.name);

    if (grantType === 'authorization_code') {
      console.log('[OAuth/Token] Processing authorization_code grant');
      return await handleAuthorizationCodeGrant(formData, client);
    } else if (grantType === 'refresh_token') {
      console.log('[OAuth/Token] Processing refresh_token grant');
      return await handleRefreshTokenGrant(formData, client);
    } else {
      console.log('[OAuth/Token] Unsupported grant type:', grantType);
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
    console.error('[OAuth/Token] POST error:', error);
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

  console.log('[OAuth/Token] Authorization code grant params:', {
    has_code: !!code,
    redirect_uri: redirectUri,
    has_code_verifier: !!codeVerifier
  });

  if (!code || !redirectUri) {
    console.log('[OAuth/Token] Missing required parameters for auth code grant');
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
  console.log('[OAuth/Token] Consuming authorization code:', code);
  const authCode = await TodoDB.consumeAuthorizationCode(
    code,
    client.client_id
  );
  if (!authCode) {
    console.log('[OAuth/Token] Invalid or expired authorization code:', code);
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

  console.log('[OAuth/Token] Authorization code consumed successfully');

  // Validate redirect URI matches
  if (authCode.redirect_uri !== redirectUri) {
    console.log('[OAuth/Token] Redirect URI mismatch:', {
      expected: authCode.redirect_uri,
      received: redirectUri
    });
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

  console.log('[OAuth/Token] Redirect URI validated');

  // Validate PKCE if used
  if (authCode.code_challenge) {
    console.log('[OAuth/Token] PKCE validation required');
    if (!codeVerifier) {
      console.log('[OAuth/Token] Code verifier missing for PKCE');
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
    console.log('[OAuth/Token] PKCE challenge method:', challengeMethod);
    let derivedChallenge;

    if (challengeMethod === 'S256') {
      derivedChallenge = crypto
        .createHash('sha256')
        .update(codeVerifier)
        .digest('base64url');
    } else if (challengeMethod === 'plain') {
      derivedChallenge = codeVerifier;
    } else {
      console.log('[OAuth/Token] Unsupported challenge method:', challengeMethod);
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
      console.log('[OAuth/Token] PKCE validation failed');
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

    console.log('[OAuth/Token] PKCE validation successful');
  }

  // Create access token
  const scopes = JSON.parse(authCode.scopes);
  console.log('[OAuth/Token] Creating access token for user:', authCode.user_id);
  const tokenData = await TodoDB.createAccessToken(
    authCode.user_id,
    client.client_id,
    scopes,
    3600 // 1 hour expiry
  );

  console.log('[OAuth/Token] Access token created successfully');

  // TODO: Implement JWT with Web Crypto API when needed

  return new Response(
    JSON.stringify({
      access_token: tokenData.token, // Use basic token for now instead of JWT
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

  console.log('[OAuth/Token] Refresh token grant params:', {
    has_refresh_token: !!refreshToken
  });

  if (!refreshToken) {
    console.log('[OAuth/Token] Missing refresh token');
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

  console.log('[OAuth/Token] Refreshing access token');
  // Refresh the access token
  const tokenData = await TodoDB.refreshAccessToken(
    refreshToken,
    client.client_id
  );
  if (!tokenData) {
    console.log('[OAuth/Token] Invalid refresh token');
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

  console.log('[OAuth/Token] Access token refreshed successfully');

  // TODO: Implement JWT with Web Crypto API when needed

  return new Response(
    JSON.stringify({
      access_token: tokenData.token, // Use basic token for now instead of JWT
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


