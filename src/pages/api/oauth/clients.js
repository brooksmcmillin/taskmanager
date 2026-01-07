import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import crypto from 'crypto';

export async function GET({ request }) {
  try {
    // Support both session and Bearer token authentication
    let session;
    try {
      session = await requireAuth(request);
    } catch (e) {
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
    };

    // Only return clients owned by this user
    const clients = await TodoDB.query(
      `
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, is_active, created_at, user_id
      FROM oauth_clients
      WHERE user_id = $1
      ORDER BY created_at DESC
    `,
      [user.id]
    );

    return new Response(JSON.stringify(clients.rows), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('[OAuth/Clients] Error:', error.message);
    return new Response('Server error', { status: 500 });
  }
}

export async function POST({ request }) {
  try {
    // Support both session and Bearer token authentication
    let session;
    try {
      session = await requireAuth(request);
    } catch (e) {
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
    };

    const body = await request.json();
    const {
      name,
      redirectUris,
      grantTypes = ['authorization_code'],
      scopes = ['read'],
      clientSecret: customSecret,
      // Support RFC 7591 token_endpoint_auth_method or explicit isPublic flag
      token_endpoint_auth_method,
      isPublic: explicitIsPublic,
    } = body;

    // Determine if this is a public client (RFC 6749 Section 2.1)
    // Public clients: native apps, SPAs, device flow clients that can't securely store secrets
    const isPublic =
      explicitIsPublic === true || token_endpoint_auth_method === 'none';

    if (
      !name ||
      !redirectUris ||
      !Array.isArray(redirectUris) ||
      redirectUris.length === 0
    ) {
      return new Response(
        JSON.stringify({
          error: 'Invalid request',
          message: 'Name and redirect URIs are required',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Public clients don't use client secrets - reject if one is provided
    if (isPublic && customSecret) {
      return new Response(
        JSON.stringify({
          error: 'Invalid request',
          message: 'Public clients cannot have a client secret',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Validate custom secret if provided - enforce strong entropy requirements
    // (only for confidential clients)
    if (
      !isPublic &&
      customSecret !== undefined &&
      customSecret !== null &&
      customSecret !== ''
    ) {
      if (typeof customSecret !== 'string') {
        return new Response(
          JSON.stringify({
            error: 'Invalid request',
            message: 'Client secret must be a string',
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      // Require minimum 32 characters for security
      if (customSecret.length < 32) {
        return new Response(
          JSON.stringify({
            error: 'Invalid request',
            message: 'Custom client secret must be at least 32 characters',
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      // Require character diversity for entropy
      const hasLower = /[a-z]/.test(customSecret);
      const hasUpper = /[A-Z]/.test(customSecret);
      const hasNumber = /[0-9]/.test(customSecret);
      const hasSpecial = /[^a-zA-Z0-9]/.test(customSecret);
      const diversityCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(
        Boolean
      ).length;

      if (diversityCount < 2) {
        return new Response(
          JSON.stringify({
            error: 'Invalid request',
            message:
              'Client secret must contain at least 2 of: lowercase, uppercase, numbers, special characters',
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
    }

    // Generate client credentials
    const clientId = crypto.randomBytes(16).toString('hex');
    // Public clients don't get a secret; confidential clients get provided or generated one
    const clientSecret = isPublic
      ? null
      : customSecret || crypto.randomBytes(32).toString('hex');

    const client = await TodoDB.createOAuthClient(
      clientId,
      clientSecret,
      name,
      redirectUris,
      grantTypes,
      scopes,
      user.id,
      isPublic
    );

    // Build response with RFC 7591 compliant fields
    const response = {
      ...client,
      token_endpoint_auth_method: isPublic ? 'none' : 'client_secret_post',
    };

    // Only include client_secret for confidential clients (return only once)
    if (!isPublic) {
      response.client_secret = clientSecret;
    }

    return new Response(JSON.stringify(response), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('[OAuth/Clients] Error:', error.message);
    return new Response('Server error', { status: 500 });
  }
}
