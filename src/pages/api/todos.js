import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';
import { errors } from '../../lib/errors.js';
import { validateRequired, validateId } from '../../lib/validators.js';
import {
  successResponse,
  createdResponse,
  formatDateString,
  jsonResponse,
} from '../../lib/apiResponse.js';

export const GET = async ({ url, request }) => {
  try {
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
      due_date: formatDateString(todo.due_date),
      status: todo.status,
      category: todo.project_name || null,
      project_name: todo.project_name || null,
      project_color: todo.project_color || null,
      priority: todo.priority,
      tags:
        typeof todo.tags === 'string' ? JSON.parse(todo.tags) : todo.tags || [],
      created_at: formatDateString(todo.created_at),
      updated_at: formatDateString(todo.updated_at),
    }));

    // Return in legacy format expected by frontend
    return successResponse({ tasks: formattedTasks });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

export const POST = async ({ request }) => {
  try {
    const session = await requireAuth(request);
    const body = await request.json();

    // Validate required fields
    const titleResult = validateRequired(body.title, 'Title');
    if (!titleResult.valid) {
      return titleResult.error.toResponse();
    }

    // Map category to project_id if provided
    let todoData = { ...body, title: titleResult.value };
    if (body.category && !body.project_id) {
      const project = await TodoDB.getProjectByName(session.user_id, body.category);
      if (project) {
        todoData.project_id = project.id;
      }
    }

    const result = await TodoDB.createTodo(session.user_id, todoData);
    return createdResponse({
      id: result.id,
      title: titleResult.value,
    });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

export const PUT = async ({ request }) => {
  try {
    const session = await requireAuth(request);
    const body = await request.json();

    // Validate ID
    const idResult = validateId(body.id, 'Todo ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const { id, ...updates } = body;
    const updated = await TodoDB.updateTodo(idResult.value, session.user_id, updates);

    if (!updated) {
      return errors.todoNotFound().toResponse();
    }

    return successResponse({ updated: true });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
