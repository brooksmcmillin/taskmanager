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
    } = body;

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

    // Validate custom secret if provided - enforce strong entropy requirements
    if (
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
      const diversityCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(Boolean).length;

      if (diversityCount < 2) {
        return new Response(
          JSON.stringify({
            error: 'Invalid request',
            message: 'Client secret must contain at least 2 of: lowercase, uppercase, numbers, special characters',
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
    const clientSecret = customSecret || crypto.randomBytes(32).toString('hex');

    const client = await TodoDB.createOAuthClient(
      clientId,
      clientSecret,
      name,
      redirectUris,
      grantTypes,
      scopes,
      user.id // Add user ownership
    );

    return new Response(
      JSON.stringify({
        ...client,
        client_secret: clientSecret, // Return secret only once
      }),
      {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    console.error('[OAuth/Clients] Error:', error.message);
    return new Response('Server error', { status: 500 });
  }
}
