import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import { errors } from '../../../lib/errors.js';
import { validateId } from '../../../lib/validators.js';
import { successResponse } from '../../../lib/apiResponse.js';

/**
 * GET /api/recurring-tasks/:id
 * Get a single recurring task by ID
 */
export const GET = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Recurring task ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const recurringTask = await TodoDB.getRecurringTaskById(
      idResult.value,
      session.user_id
    );

    if (!recurringTask) {
      return errors.recurringTaskNotFound().toResponse();
    }

    return successResponse(recurringTask);
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

/**
 * PUT /api/recurring-tasks/:id
 * Update a recurring task
 *
 * Body can include any of:
 *   - title, frequency, interval_value, weekdays, day_of_month
 *   - start_date, end_date, next_due_date
 *   - project_id, description, priority, estimated_hours, tags, context
 *   - skip_missed, is_active
 */
export const PUT = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Recurring task ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    // Check if recurring task exists and belongs to user
    const existing = await TodoDB.getRecurringTaskById(
      idResult.value,
      session.user_id
    );
    if (!existing) {
      return errors.recurringTaskNotFound().toResponse();
    }

    const updates = await request.json();

    // Validate frequency if provided
    if (updates.frequency) {
      const validFrequencies = ['daily', 'weekly', 'monthly', 'yearly'];
      if (!validFrequencies.includes(updates.frequency)) {
        return errors
          .invalid(
            'Frequency',
            `must be one of: ${validFrequencies.join(', ')}`
          )
          .toResponse();
      }
    }

    // Validate weekdays if provided
    if (updates.weekdays) {
      if (!Array.isArray(updates.weekdays)) {
        return errors.invalid('Weekdays', 'must be an array').toResponse();
      }
      for (const day of updates.weekdays) {
        if (!Number.isInteger(day) || day < 0 || day > 6) {
          return errors
            .invalid('Weekdays', 'must contain integers 0-6 (Sunday-Saturday)')
            .toResponse();
        }
      }
    }

    // Validate day_of_month if provided
    if (updates.day_of_month !== undefined && updates.day_of_month !== null) {
      if (
        !Number.isInteger(updates.day_of_month) ||
        updates.day_of_month < 1 ||
        updates.day_of_month > 31
      ) {
        return errors
          .invalid('Day of month', 'must be an integer 1-31')
          .toResponse();
      }
    }

    // Validate project_id if provided
    if (updates.project_id) {
      const projectIdResult = validateId(updates.project_id, 'Project ID');
      if (!projectIdResult.valid) {
        return projectIdResult.error.toResponse();
      }

      const project = await TodoDB.getProjectById(
        projectIdResult.value,
        session.user_id
      );
      if (!project) {
        return errors.projectNotFound().toResponse();
      }
    }

    // Validate priority if provided
    if (updates.priority) {
      const validPriorities = ['low', 'medium', 'high', 'urgent'];
      if (!validPriorities.includes(updates.priority)) {
        return errors
          .invalid('Priority', `must be one of: ${validPriorities.join(', ')}`)
          .toResponse();
      }
    }

    const updatedTask = await TodoDB.updateRecurringTask(
      idResult.value,
      session.user_id,
      updates
    );

    return successResponse(updatedTask);
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    if (error.message === 'No valid fields to update') {
      return errors.validation('No valid fields to update').toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

/**
 * DELETE /api/recurring-tasks/:id
 * Deactivate a recurring task (soft delete)
 */
export const DELETE = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Recurring task ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    // Check if recurring task exists and belongs to user
    const existing = await TodoDB.getRecurringTaskById(
      idResult.value,
      session.user_id
    );
    if (!existing) {
      return errors.recurringTaskNotFound().toResponse();
    }

    await TodoDB.deleteRecurringTask(idResult.value, session.user_id);

    return successResponse({ deleted: true });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
