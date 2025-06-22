import { Auth } from '../../../lib/auth.js';

export async function GET({ request }) {
  try {
    const sessionId = Auth.getSessionFromRequest(request);
    const session = Auth.getSessionUser(sessionId);
    
    if (!session) {
      return new Response(JSON.stringify({ error: 'Not authenticated' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response(JSON.stringify({ 
      user: { 
        id: session.user_id, 
        username: session.username, 
        email: session.email 
      }
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });

  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}