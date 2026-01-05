import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import {
  successResponse,
  errorResponse,
  notFoundResponse,
} from '../../../lib/apiResponse.js';

export const GET = async ({ params, request }) => {
  const session = await requireAuth(request);
  const todoId = parseInt(params.id);

  if (!todoId) {
    return errorResponse('Invalid todo ID');
  }

  const todo = await TodoDB.getTodoById(todoId, session.user_id);

  if (!todo) {
    return notFoundResponse('Todo not found');
  }

  return successResponse(todo);
};

export const PUT = async ({ params, request }) => {
  const session = await requireAuth(request);
  const todoId = parseInt(params.id);
  const updates = await request.json();

  if (!todoId) {
    return errorResponse('Invalid todo ID');
  }

  // Check if todo exists and belongs to user
  const todo = await TodoDB.getTodoById(todoId, session.user_id);
  if (!todo) {
    return notFoundResponse('Todo not found');
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

  return successResponse({
    id: todoId,
    updated_fields: updatedFields,
    status: 'updated',
  });
};

export const DELETE = async ({ params, request }) => {
  const session = await requireAuth(request);
  const todoId = parseInt(params.id);

  if (!todoId) {
    return errorResponse('Invalid todo ID');
  }

  // Check if todo exists and belongs to user
  const todo = await TodoDB.getTodoById(todoId, session.user_id);
  if (!todo) {
    return notFoundResponse('Todo not found');
  }

  await TodoDB.deleteTodo(todoId, session.user_id);

  return successResponse({ success: true });
};
