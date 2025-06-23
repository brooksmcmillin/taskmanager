import { TodoDB } from '../../../../lib/db.js';
import { Auth } from '../../../../lib/auth.js';

async function requireAuth(request) {
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);
  
  if (!session) {
    throw new Error('Authentication required');
  }
  
  return session;
}

export const POST = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);
    const { id } = params;
    const { actual_hours } = await request.json();
    
    if (!id || !actual_hours) {
      return new Response(JSON.stringify({ error: 'Missing id or actual_hours' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    await TodoDB.completeTodo(parseInt(id), session.user_id, parseFloat(actual_hours));
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error completing todo:', error);
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
