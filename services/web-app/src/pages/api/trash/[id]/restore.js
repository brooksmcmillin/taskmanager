import { TodoDB } from '../../../../lib/db.js';
import { requireAuth } from '../../../../lib/auth.js';
import { errors } from '../../../../lib/errors.js';
import { validateId } from '../../../../lib/validators.js';
import { successResponse } from '../../../../lib/apiResponse.js';

export const POST = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Todo ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    // Check if deleted todo exists
    const todo = await TodoDB.getDeletedTodoById(
      idResult.value,
      session.user_id
    );
    if (!todo) {
      return errors.notFound('Deleted task').toResponse();
    }

    const restored = await TodoDB.restoreTodo(idResult.value, session.user_id);

    return successResponse({ restored: true, id: restored.id });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
