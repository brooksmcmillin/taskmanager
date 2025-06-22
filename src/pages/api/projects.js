import { TodoDB } from '../../lib/db.js';
import { Auth } from '../../lib/auth.js';

function requireAuth(request) {
  const sessionId = Auth.getSessionFromRequest(request);
  const session = Auth.getSessionUser(sessionId);
  
  if (!session) {
    throw new Error('Authentication required');
  }
  
  return session;
}

export const GET = async ({ request }) => {
  try {
    const session = requireAuth(request);
    const projects = TodoDB.getProjects(session.user_id);
    return new Response(JSON.stringify(projects), {
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
    const session = requireAuth(request);
    const body = await request.json();
    const result = TodoDB.createProject(session.user_id, body.name, body.description, body.color);
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
