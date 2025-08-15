import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';

export const GET = async ({ url, request }) => {
  const session = await requireAuth(request);
  const searchParams = new URL(url).searchParams;
  const projectId = searchParams.get('project_id');
  const status = searchParams.get('status');
  const dueDate = searchParams.get('due_date');

  const todos = await TodoDB.getTodos(
    session.user_id,
    projectId,
    status,
    dueDate
  );
  return new Response(JSON.stringify(todos), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

export const POST = async ({ request }) => {
  const session = await requireAuth(request);
  const body = await request.json();
  const result = await TodoDB.createTodo(session.user_id, body);
  return new Response(JSON.stringify({ id: result.lastInsertRowid }), {
    status: 201,
    headers: { 'Content-Type': 'application/json' },
  });
};

export const PUT = async ({ request }) => {
  const session = await requireAuth(request);
  const body = await request.json();
  const { id, ...updates } = body;
  await TodoDB.updateTodo(id, session.user_id, updates);
  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
