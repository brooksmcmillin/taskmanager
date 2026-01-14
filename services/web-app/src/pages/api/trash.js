import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';
import { errors } from '../../lib/errors.js';
import { successResponse, formatDateString } from '../../lib/apiResponse.js';

export const GET = async ({ url, request }) => {
  try {
    const session = await requireAuth(request);
    const searchParams = new URL(url).searchParams;
    const query = searchParams.get('query');

    let todos;
    if (query && query.trim()) {
      todos = await TodoDB.searchDeletedTodos(session.user_id, query.trim());
    } else {
      todos = await TodoDB.getDeletedTodos(session.user_id);
    }

    const formattedTasks = todos.map((todo) => ({
      id: todo.id,
      title: todo.title,
      description: todo.description || '',
      due_date: formatDateString(todo.due_date),
      status: todo.status,
      project_name: todo.project_name || null,
      project_color: todo.project_color || null,
      priority: todo.priority,
      tags:
        typeof todo.tags === 'string' ? JSON.parse(todo.tags) : todo.tags || [],
      deleted_at: formatDateString(todo.deleted_at),
      created_at: formatDateString(todo.created_at),
    }));

    return successResponse({
      tasks: formattedTasks,
      count: formattedTasks.length,
    });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
