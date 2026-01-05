import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';

export const GET = async ({ url, request }) => {
  const session = await requireAuth(request);
  const searchParams = new URL(url).searchParams;
  const projectId = searchParams.get('project_id');
  const status = searchParams.get('status');
  const startDate = searchParams.get('start_date');
  const endDate = searchParams.get('end_date');
  const category = searchParams.get('category');
  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : null;

  const todos = await TodoDB.getTodosFiltered(session.user_id, {
    projectId,
    status,
    startDate,
    endDate,
    category,
    limit,
  });

  // Format response to match expected API structure
  const formattedTasks = todos.map((todo) => ({
    id: todo.id,
    title: todo.title,
    description: todo.description || '',
    due_date: todo.due_date
      ? new Date(todo.due_date).toISOString().split('T')[0]
      : null,
    status: todo.status,
    category: todo.project_name || null,
    project_name: todo.project_name || null,
    project_color: todo.project_color || null,
    priority: todo.priority,
    tags:
      typeof todo.tags === 'string' ? JSON.parse(todo.tags) : todo.tags || [],
    created_at: todo.created_at
      ? new Date(todo.created_at).toISOString().split('T')[0]
      : null,
    updated_at: todo.updated_at
      ? new Date(todo.updated_at).toISOString().split('T')[0]
      : null,
  }));

  return new Response(JSON.stringify({ tasks: formattedTasks }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

export const POST = async ({ request }) => {
  const session = await requireAuth(request);
  const body = await request.json();

  // Map category to project_id if provided
  let todoData = { ...body };
  if (body.category && !body.project_id) {
    // Look up project by name to get project_id
    const projects = await TodoDB.getProjects(session.user_id);
    const project = projects.find(
      (p) => p.name.toLowerCase() === body.category.toLowerCase()
    );
    if (project) {
      todoData.project_id = project.id;
    }
  }

  const result = await TodoDB.createTodo(session.user_id, todoData);
  return new Response(
    JSON.stringify({
      id: result.id,
      title: body.title,
      status: 'created',
    }),
    {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    }
  );
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
