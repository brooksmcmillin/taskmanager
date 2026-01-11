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

    // Use completeRecurringTodo which handles both regular and recurring tasks
    // For recurring tasks with skip_missed=true, it recalculates the next due date from today
    const result = await TodoDB.completeRecurringTodo(
      idResult.value,
      session.user_id
    );

    if (!result) {
      return errors.todoNotFound().toResponse();
    }

    return successResponse({
      success: true,
      recurring: result.recurring
        ? { next_due_date: result.recurring.next_due_date }
        : null,
    });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
