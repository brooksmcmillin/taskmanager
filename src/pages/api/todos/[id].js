import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';

export const GET = async ({ params, request }) => {
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
};

export const PUT = async ({ params, request }) => {
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
};

export const DELETE = async ({ params, request }) => {
  const session = await requireAuth(request);
  const todoId = parseInt(params.id);

  if (!todoId) {
    return new Response(JSON.stringify({ error: 'Invalid todo ID' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Check if todo exists and belongs to user
  const todo = await TodoDB.getTodoById(todoId, session.user_id);
  if (!todo) {
    return new Response(JSON.stringify({ error: 'Todo not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  await TodoDB.deleteTodo(todoId);

  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
