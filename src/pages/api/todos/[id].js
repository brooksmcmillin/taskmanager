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

  // Check if todo exists and belongs to user
  const todo = await TodoDB.getTodoById(todoId, session.user_id);
  if (!todo) {
    return new Response(JSON.stringify({ error: 'Todo not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Map category to project_id if provided
  let updateData = { ...updates };
  if (updates.category && !updates.project_id) {
    const projects = await TodoDB.getProjects(session.user_id);
    const project = projects.find(
      (p) => p.name.toLowerCase() === updates.category.toLowerCase()
    );
    if (project) {
      updateData.project_id = project.id;
    }
    delete updateData.category;
  }

  // Track which fields are being updated
  const updatedFields = Object.keys(updates);

  await TodoDB.updateTodo(todoId, session.user_id, updateData);

  return new Response(
    JSON.stringify({
      id: todoId,
      updated_fields: updatedFields,
      status: 'updated',
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
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
