import { TodoDB } from '../../../../lib/db.js';
import { Auth } from '../../../../lib/auth.js';

export async function PUT({ request, params }) {
  try {
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return new Response('Unauthorized', { status: 401 });
    }

    const body = await request.json();
    const {
      name,
      redirectUris,
      grantTypes = ['authorization_code'],
      scopes = ['read'],
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

    const result = await TodoDB.query(
      `
      UPDATE oauth_clients
      SET name = $1, redirect_uris = $2, grant_types = $3, scopes = $4
      WHERE client_id = $5
      RETURNING id, client_id, name, redirect_uris, grant_types, scopes, is_active, created_at
    `,
      [
        name,
        JSON.stringify(redirectUris),
        JSON.stringify(grantTypes),
        JSON.stringify(scopes),
        params.clientId,
      ]
    );

    if (result.rows.length === 0) {
      return new Response(
        JSON.stringify({ error: 'Client not found' }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(JSON.stringify(result.rows[0]), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('Update OAuth client error:', error);
    return new Response('Server error', { status: 500 });
  }
}

export async function DELETE({ request, params }) {
  try {
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return new Response('Unauthorized', { status: 401 });
    }

    const result = await TodoDB.query(
      `
      DELETE FROM oauth_clients
      WHERE client_id = $1
      RETURNING client_id
    `,
      [params.clientId]
    );

    if (result.rows.length === 0) {
      return new Response(
        JSON.stringify({ error: 'Client not found' }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    return new Response(
      JSON.stringify({ message: 'Client deleted successfully' }),
      {
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    console.error('Delete OAuth client error:', error);
    return new Response('Server error', { status: 500 });
  }
}
