import crypto from 'crypto';
import { oauthErrors } from './apiResponse.js';

/**
 * OAuth helper utilities
 * Consolidates common OAuth validation and processing logic
 */

/**
 * Validate that an OAuth client is authorized for a specific grant type
 * @param {Object} client - OAuth client object with grant_types field
 * @param {string} grantType - Grant type to validate (e.g., 'authorization_code', 'device_code')
 * @returns {Response|null} Error response if invalid, null if valid
 */
export function validateGrantType(client, grantType) {
  const allowedGrantTypes = JSON.parse(client.grant_types || '[]');
  if (!allowedGrantTypes.includes(grantType)) {
    return oauthErrors.unauthorizedClient(
      `Client is not authorized to use ${grantType} grant`
    );
  }
  return null;
}

/**
 * Validate and parse requested scopes against client's allowed scopes
 * @param {string|null} requestedScope - Space-separated scope string from request
 * @param {Object} client - OAuth client object with scopes field
 * @returns {{ scopes: string[]|null, error: Response|null }} Scopes array or error response
 */
export function validateScopes(requestedScope, client) {
  const clientScopes = JSON.parse(client.scopes || '["read"]');

  // If no scope requested, use client's default scopes
  if (!requestedScope) {
    return { scopes: clientScopes, error: null };
  }

  // Parse and validate requested scopes
  const requestedScopes = requestedScope.split(' ').filter(Boolean);
  const invalidScopes = requestedScopes.filter((s) => !clientScopes.includes(s));

  if (invalidScopes.length > 0) {
    return {
      scopes: null,
      error: oauthErrors.invalidScope(invalidScopes.join(', ')),
    };
  }

  return { scopes: requestedScopes, error: null };
}

/**
 * Validate PKCE code verifier against stored code challenge
 * @param {string} codeVerifier - The code_verifier from the token request
 * @param {string} codeChallenge - The stored code_challenge from authorization
 * @param {string} codeChallengeMethod - 'S256' or 'plain'
 * @returns {Response|null} Error response if invalid, null if valid
 */
export function validatePKCE(codeVerifier, codeChallenge, codeChallengeMethod) {
  if (!codeVerifier) {
    return oauthErrors.invalidRequest('Code verifier required for PKCE');
  }

  const method = codeChallengeMethod || 'plain';
  let derivedChallenge;

  if (method === 'S256') {
    derivedChallenge = crypto
      .createHash('sha256')
      .update(codeVerifier)
      .digest('base64url');
  } else if (method === 'plain') {
    derivedChallenge = codeVerifier;
  } else {
    return oauthErrors.invalidRequest('Unsupported code challenge method');
  }

  if (derivedChallenge !== codeChallenge) {
    return oauthErrors.invalidGrant('Code verifier validation failed');
  }

  return null;
}

/**
 * Check if client has an owner for client_credentials grant
 * @param {Object} client - OAuth client object
 * @returns {Response|null} Error response if no owner, null if valid
 */
export function validateClientOwner(client) {
  if (!client.user_id) {
    return oauthErrors.serverError('Client configuration error: no owner assigned');
  }
  return null;
}
