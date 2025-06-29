import { TodoDB } from '../../../lib/db.js';
import crypto from 'crypto';
import jwt from 'jsonwebtoken';
import fs from 'fs';

export async function POST({ request }) {
  try {
    const formData = await request.formData();
    const grantType = formData.get('grant_type');
    const clientId = formData.get('client_id');
    const clientSecret = formData.get('client_secret');

    // Validate client credentials
    const client = await TodoDB.validateOAuthClient(clientId, clientSecret);
    if (!client) {
      return new Response(JSON.stringify({
        error: 'invalid_client',
        error_description: 'Invalid client credentials'
      }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (grantType === 'authorization_code') {
      return await handleAuthorizationCodeGrant(formData, client);
    } else if (grantType === 'refresh_token') {
      return await handleRefreshTokenGrant(formData, client);
    } else {
      return new Response(JSON.stringify({
        error: 'unsupported_grant_type',
        error_description: 'Grant type not supported'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
  } catch (error) {
    console.error('OAuth token error:', error);
    return new Response(JSON.stringify({
      error: 'server_error',
      error_description: 'Internal server error'
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function handleAuthorizationCodeGrant(formData, client) {
  const code = formData.get('code');
  const redirectUri = formData.get('redirect_uri');
  const codeVerifier = formData.get('code_verifier');

  if (!code || !redirectUri) {
    return new Response(JSON.stringify({
      error: 'invalid_request',
      error_description: 'Missing required parameters'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Consume authorization code
  const authCode = await TodoDB.consumeAuthorizationCode(code, client.client_id);
  if (!authCode) {
    return new Response(JSON.stringify({
      error: 'invalid_grant',
      error_description: 'Invalid or expired authorization code'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Validate redirect URI matches
  if (authCode.redirect_uri !== redirectUri) {
    return new Response(JSON.stringify({
      error: 'invalid_grant',
      error_description: 'Redirect URI mismatch'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Validate PKCE if used
  if (authCode.code_challenge) {
    if (!codeVerifier) {
      return new Response(JSON.stringify({
        error: 'invalid_request',
        error_description: 'Code verifier required for PKCE'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    const challengeMethod = authCode.code_challenge_method || 'plain';
    let derivedChallenge;
    
    if (challengeMethod === 'S256') {
      derivedChallenge = crypto.createHash('sha256')
        .update(codeVerifier)
        .digest('base64url');
    } else if (challengeMethod === 'plain') {
      derivedChallenge = codeVerifier;
    } else {
      return new Response(JSON.stringify({
        error: 'invalid_request',
        error_description: 'Unsupported code challenge method'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    if (derivedChallenge !== authCode.code_challenge) {
      return new Response(JSON.stringify({
        error: 'invalid_grant',
        error_description: 'Code verifier validation failed'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
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

  // Create JWT access token for MCP authentication
  const jwtToken = await createJWTToken(authCode.user_id, client.client_id, scopes);

  return new Response(JSON.stringify({
    access_token: jwtToken, // Use JWT instead of random token
    token_type: 'Bearer',
    expires_in: 3600,
    refresh_token: tokenData.refresh_token,
    scope: scopes.join(' ')
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

async function handleRefreshTokenGrant(formData, client) {
  const refreshToken = formData.get('refresh_token');

  if (!refreshToken) {
    return new Response(JSON.stringify({
      error: 'invalid_request',
      error_description: 'Missing refresh token'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Refresh the access token
  const tokenData = await TodoDB.refreshAccessToken(refreshToken, client.client_id);
  if (!tokenData) {
    return new Response(JSON.stringify({
      error: 'invalid_grant',
      error_description: 'Invalid refresh token'
    }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' }
    });
  }

  // Create JWT access token for MCP authentication
  const jwtToken = await createJWTToken(tokenData.user_id, client.client_id, tokenData.scopes);

  return new Response(JSON.stringify({
    access_token: jwtToken, // Use JWT instead of random token
    token_type: 'Bearer',
    expires_in: 3600,
    refresh_token: tokenData.refresh_token
  }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  });
}

// JWT token creation function
async function createJWTToken(userId, clientId, scopes) {
  try {
    // TODO: Replace with path to your private key
    // Generate with: openssl genrsa -out private.pem 2048
    const privateKey = process.env.JWT_PRIVATE_KEY || 'REPLACE_WITH_PRIVATE_KEY_PEM';
    
    const payload = {
      sub: userId.toString(),
      client_id: clientId,
      scopes: Array.isArray(scopes) ? scopes : JSON.parse(scopes || '["read"]'),
      iss: process.env.JWT_ISSUER || 'http://localhost:4321',
      aud: 'taskmanager-mcp',
      iat: Math.floor(Date.now() / 1000),
      exp: Math.floor(Date.now() / 1000) + 3600 // 1 hour
    };

    return jwt.sign(payload, privateKey, {
      algorithm: 'RS256',
      keyid: 'taskmanager-mcp-key-1'
    });
  } catch (error) {
    console.error('JWT creation error:', error);
    // Fallback to basic token if JWT fails
    return crypto.randomBytes(32).toString('hex');
  }
}