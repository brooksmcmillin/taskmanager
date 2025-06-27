import { TodoDB } from '../../../lib/db.js';
import { Auth } from '../../../lib/auth.js';

async function requireAuth(request) {
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);

  if (!session) {
    throw new Error('Authentication required');
  }

  return session;
}

export const GET = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);
    const todoId = parseInt(params.id);

    if (!todoId) {
      return new Response(JSON.stringify({ error: 'Invalid todo ID' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    const todo = await TodoDB.getTodoById(todoId, session.user_id);

    if (!todo) {
      return new Response(JSON.stringify({ error: 'Todo not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    return new Response(JSON.stringify(todo), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};

export const PUT = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);
    const todoId = parseInt(params.id);
    const updates = await request.json();

    if (!todoId) {
      return new Response(JSON.stringify({ error: 'Invalid todo ID' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    await TodoDB.updateTodo(todoId, session.user_id, updates);

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
