import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import {
  successResponse,
  errorResponse,
  formatDateString,
} from '../../../lib/apiResponse.js';

export const GET = async ({ url, request }) => {
  const session = await requireAuth(request);
  const searchParams = new URL(url).searchParams;
  const query = searchParams.get('query');
  const category = searchParams.get('category');

  if (!query) {
    return errorResponse('Query parameter is required');
  }

  const todos = await TodoDB.searchTodos(session.user_id, query, category);

  const formattedTasks = todos.map((todo) => ({
    id: `task_${todo.id}`,
    title: todo.title,
    description: todo.description || '',
    due_date: formatDateString(todo.due_date),
    status: todo.status,
    category: todo.project_name || null,
    priority: todo.priority,
    tags:
      typeof todo.tags === 'string' ? JSON.parse(todo.tags) : todo.tags || [],
    created_at: formatDateString(todo.created_at),
    updated_at: formatDateString(todo.updated_at),
  }));

  return successResponse({
    tasks: formattedTasks,
    count: formattedTasks.length,
  });
};
