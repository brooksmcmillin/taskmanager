import { TodoDB } from '../../../lib/db.js';
import { Auth } from '../../../lib/auth.js';
import crypto from 'crypto';

export async function GET({ request }) {
  try {
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    // For now, only allow admin users to view clients
    // You may want to add an admin role check here

    const clients = await TodoDB.query(`
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, is_active, created_at
      FROM oauth_clients 
      ORDER BY created_at DESC
    `);

    return new Response(JSON.stringify(clients.rows), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('Get OAuth clients error:', error);
    return new Response('Server error', { status: 500 });
  }
}

export async function POST({ request }) {
  try {
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return new Response('Unauthorized', { status: 401 });
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
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

    // Validate custom secret if provided
    if (customSecret !== undefined && customSecret !== null && customSecret !== '') {
      if (typeof customSecret !== 'string' || customSecret.length < 11) {
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

    const client = await TodoDB.createOAuthClient(
      clientId,
      clientSecret,
      name,
      redirectUris,
      grantTypes,
      scopes
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
    console.error('Create OAuth client error:', error);
    return new Response('Server error', { status: 500 });
  }
}
