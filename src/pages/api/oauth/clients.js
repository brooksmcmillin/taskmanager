import { TodoDB } from '../../../lib/db.js';
import { Auth } from '../../../lib/auth.js';
import crypto from 'crypto';

export async function GET({ request }) {
  try {
    console.log('[OAuth/Clients] GET request received');
    const sessionId = Auth.getSessionFromRequest(request);
    console.log(
      '[OAuth/Clients] Session ID:',
      sessionId ? 'present' : 'missing'
    );

    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Clients] GET unauthorized - no valid session');
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    console.log('[OAuth/Clients] GET authorized for user:', user.username);

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

    console.log(
      '[OAuth/Clients] Returning',
      clients.rows.length,
      'clients for user:',
      user.id
    );

    return new Response(JSON.stringify(clients.rows), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('[OAuth/Clients] GET error:', error);
    return new Response('Server error', { status: 500 });
  }
}

export async function POST({ request }) {
  try {
    console.log('[OAuth/Clients] POST request received');
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Clients] POST unauthorized - no valid session');
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    console.log('[OAuth/Clients] POST authorized for user:', user.username);

    const body = await request.json();
    const {
      name,
      redirectUris,
      grantTypes = ['authorization_code'],
      scopes = ['read'],
      clientSecret: customSecret,
    } = body;

    console.log('[OAuth/Clients] Creating client:', {
      name,
      redirectUris,
      grantTypes,
      scopes,
      hasCustomSecret: !!customSecret,
    });

    if (
      !name ||
      !redirectUris ||
      !Array.isArray(redirectUris) ||
      redirectUris.length === 0
    ) {
      console.log(
        '[OAuth/Clients] POST validation failed - missing required fields'
      );
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

    // Validate custom secret if provided
    if (
      customSecret !== undefined &&
      customSecret !== null &&
      customSecret !== ''
    ) {
      if (typeof customSecret !== 'string' || customSecret.length < 11) {
        console.log(
          '[OAuth/Clients] POST validation failed - custom secret too short'
        );
        return new Response(
          JSON.stringify({
            error: 'Invalid request',
            message: 'Custom client secret must be at least 16 characters',
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
    console.log('[OAuth/Clients] Generated client_id:', clientId);

    const client = await TodoDB.createOAuthClient(
      clientId,
      clientSecret,
      name,
      redirectUris,
      grantTypes,
      scopes,
      user.id // Add user ownership
    );

    console.log(
      '[OAuth/Clients] Client created successfully for user:',
      user.id,
      '- client_id:',
      client.client_id
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
    console.error('[OAuth/Clients] POST error:', error);
    return new Response('Server error', { status: 500 });
  }
}
