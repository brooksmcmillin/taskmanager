import { TodoDB } from '../../../../lib/db.js';
import { Auth } from '../../../../lib/auth.js';

export async function PUT({ request, params }) {
  try {
    console.log('[OAuth/Clients] PUT request received for client_id:', params.clientId);
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Clients] PUT unauthorized - no valid session');
      return new Response('Unauthorized', { status: 401 });
    }

    console.log('[OAuth/Clients] PUT authorized for user:', session.username);

    const body = await request.json();
    const {
      name,
      redirectUris,
      grantTypes = ['authorization_code'],
      scopes = ['read'],
    } = body;

    console.log('[OAuth/Clients] Updating client:', {
      client_id: params.clientId,
      name,
      redirectUris,
      grantTypes,
      scopes
    });

    if (
      !name ||
      !redirectUris ||
      !Array.isArray(redirectUris) ||
      redirectUris.length === 0
    ) {
      console.log('[OAuth/Clients] PUT validation failed - missing required fields');
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

    // Verify ownership before updating
    const result = await TodoDB.query(
      `
      UPDATE oauth_clients
      SET name = $1, redirect_uris = $2, grant_types = $3, scopes = $4
      WHERE client_id = $5 AND user_id = $6
      RETURNING id, client_id, name, redirect_uris, grant_types, scopes, is_active, created_at, user_id
    `,
      [
        name,
        JSON.stringify(redirectUris),
        JSON.stringify(grantTypes),
        JSON.stringify(scopes),
        params.clientId,
        session.user_id,  // Verify ownership
      ]
    );

    if (result.rows.length === 0) {
      console.log('[OAuth/Clients] PUT failed - client not found or unauthorized:', params.clientId);
      return new Response(
        JSON.stringify({ error: 'Client not found or you do not have permission to modify it' }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }
    console.log('[OAuth/Clients] Client updated successfully by user:', session.user_id, '- client_id:', params.clientId);

    return new Response(JSON.stringify(result.rows[0]), {
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    console.error('[OAuth/Clients] PUT error:', error);
    return new Response('Server error', { status: 500 });
  }
}

export async function DELETE({ request, params }) {
  try {
    console.log('[OAuth/Clients] DELETE request received for client_id:', params.clientId);
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Clients] DELETE unauthorized - no valid session');
      return new Response('Unauthorized', { status: 401 });
    }

    console.log('[OAuth/Clients] DELETE authorized for user:', session.username);

    // Verify ownership before deleting
    const result = await TodoDB.query(
      `
      DELETE FROM oauth_clients
      WHERE client_id = $1 AND user_id = $2
      RETURNING client_id
    `,
      [params.clientId, session.user_id]
    );

    if (result.rows.length === 0) {
      console.log('[OAuth/Clients] DELETE failed - client not found or unauthorized:', params.clientId);
      return new Response(
        JSON.stringify({ error: 'Client not found or you do not have permission to delete it' }),
        {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    console.log('[OAuth/Clients] Client deleted successfully by user:', session.user_id, '- client_id:', params.clientId);

    console.error('[OAuth/Clients] DELETE error:', error);
    return new Response('Server error', { status: 500 });
  }
}
