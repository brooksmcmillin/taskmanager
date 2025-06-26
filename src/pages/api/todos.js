import { TodoDB } from '../../lib/db.js';
import { Auth } from '../../lib/auth.js';

async function requireAuth(request) {
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);
  
  if (!session) {
    throw new Error('Authentication required');
  }
  
  return session;
}

export const GET = async ({ url, request }) => {
  try {
    const session = await requireAuth(request);
    const searchParams = new URL(url).searchParams;
    const projectId = searchParams.get('project_id');
    const status = searchParams.get('status');
    const timeHorizon = searchParams.get('time_horizon');
    
    const todos = await TodoDB.getTodos(session.user_id, projectId, status, timeHorizon);
    return new Response(JSON.stringify(todos), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};

export const POST = async ({ request }) => {
  try {
    const session = await requireAuth(request);
    const body = await request.json();
    const result = await TodoDB.createTodo(session.user_id, body);
    return new Response(JSON.stringify({ id: result.lastInsertRowid }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};

export const PUT = async ({ request }) => {
  try {
    const session = await requireAuth(request);
    const body = await request.json();
    const { id, ...updates } = body;
    await TodoDB.updateTodo(id, session.user_id, updates);
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
