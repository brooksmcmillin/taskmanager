import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import { errors } from '../../../lib/errors.js';
import { validateId } from '../../../lib/validators.js';
import { successResponse } from '../../../lib/apiResponse.js';

export const GET = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Todo ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const todo = await TodoDB.getTodoById(idResult.value, session.user_id);

    if (!todo) {
      return errors.todoNotFound().toResponse();
    }

    return successResponse(todo);
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

export const PUT = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Todo ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const updates = await request.json();

    // Check if todo exists and belongs to user
    const todo = await TodoDB.getTodoById(idResult.value, session.user_id);
    if (!todo) {
      return errors.todoNotFound().toResponse();
    }

    // Map category to project_id if provided (using direct lookup instead of N+1 query)
    let updateData = { ...updates };
    if (updates.category && !updates.project_id) {
      const project = await TodoDB.getProjectByName(session.user_id, updates.category);
      if (project) {
        updateData.project_id = project.id;
      }
      delete updateData.category;
    }

    // Track which fields are being updated
    const updatedFields = Object.keys(updates);

    await TodoDB.updateTodo(idResult.value, session.user_id, updateData);

    return successResponse({
      id: idResult.value,
      updated_fields: updatedFields,
      status: 'updated',
    });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

export const DELETE = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Todo ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    // Check if todo exists and belongs to user
    const todo = await TodoDB.getTodoById(idResult.value, session.user_id);
    if (!todo) {
      return errors.todoNotFound().toResponse();
    }

    await TodoDB.deleteTodo(idResult.value, session.user_id);

    return successResponse({ deleted: true });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
