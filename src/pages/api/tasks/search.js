import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';

export const GET = async ({ url, request }) => {
  const session = await requireAuth(request);
  const searchParams = new URL(url).searchParams;
  const query = searchParams.get('query');
  const category = searchParams.get('category');

  if (!query) {
    return new Response(
      JSON.stringify({ error: 'Query parameter is required' }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  const todos = await TodoDB.searchTodos(session.user_id, query, category);

  const formattedTasks = todos.map((todo) => ({
    id: `task_${todo.id}`,
    title: todo.title,
    description: todo.description || '',
    due_date: todo.due_date
      ? new Date(todo.due_date).toISOString().split('T')[0]
      : null,
    status: todo.status,
    category: todo.project_name || null,
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

  return new Response(
    JSON.stringify({
      tasks: formattedTasks,
      count: formattedTasks.length,
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }
  );
};
