import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import { errors } from '../../../lib/errors.js';
import { validateRequired, validateId } from '../../../lib/validators.js';
import { successResponse, createdResponse } from '../../../lib/apiResponse.js';

/**
 * GET /api/recurring-tasks
 * List all recurring tasks for the authenticated user
 *
 * Query params:
 *   - active_only: boolean (default: true) - Only return active recurring tasks
 */
export const GET = async ({ request, url }) => {
  try {
    const session = await requireAuth(request);

    const activeOnly = url.searchParams.get('active_only') !== 'false';

    const recurringTasks = await TodoDB.getRecurringTasks(
      session.user_id,
      activeOnly
    );

    return successResponse({ recurring_tasks: recurringTasks });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};

/**
 * POST /api/recurring-tasks
 * Create a new recurring task
 *
 * Body:
 *   - title: string (required)
 *   - frequency: 'daily' | 'weekly' | 'monthly' | 'yearly' (required)
 *   - start_date: string YYYY-MM-DD (required)
 *   - interval_value: number (default: 1)
 *   - weekdays: number[] (for weekly, 0=Sunday..6=Saturday)
 *   - day_of_month: number (for monthly, 1-31)
 *   - end_date: string YYYY-MM-DD (optional)
 *   - project_id: number (optional)
 *   - description: string (optional)
 *   - priority: 'low' | 'medium' | 'high' | 'urgent' (default: 'medium')
 *   - estimated_hours: number (default: 1.0)
 *   - tags: string[] (optional)
 *   - context: string (default: 'work')
 *   - skip_missed: boolean (default: true)
 */
export const POST = async ({ request }) => {
  try {
    const session = await requireAuth(request);

    const body = await request.json();

    // Validate required fields
    const titleResult = validateRequired(body.title, 'Title');
    if (!titleResult.valid) {
      return titleResult.error.toResponse();
    }

    const frequencyResult = validateRequired(body.frequency, 'Frequency');
    if (!frequencyResult.valid) {
      return frequencyResult.error.toResponse();
    }

    // Validate frequency value
    const validFrequencies = ['daily', 'weekly', 'monthly', 'yearly'];
    if (!validFrequencies.includes(body.frequency)) {
      return errors
        .invalid(
          'Frequency',
          `must be one of: ${validFrequencies.join(', ')}`
        )
        .toResponse();
    }

    const startDateResult = validateRequired(body.start_date, 'Start date');
    if (!startDateResult.valid) {
      return startDateResult.error.toResponse();
    }

    // Validate start_date format
    if (!/^\d{4}-\d{2}-\d{2}$/.test(body.start_date)) {
      return errors
        .invalid('Start date', 'must be in YYYY-MM-DD format')
        .toResponse();
    }

    // Validate weekdays if provided
    if (body.weekdays) {
      if (!Array.isArray(body.weekdays)) {
        return errors.invalid('Weekdays', 'must be an array').toResponse();
      }
      for (const day of body.weekdays) {
        if (!Number.isInteger(day) || day < 0 || day > 6) {
          return errors
            .invalid('Weekdays', 'must contain integers 0-6 (Sunday-Saturday)')
            .toResponse();
        }
      }
    }

    // Validate day_of_month if provided
    if (body.day_of_month !== undefined && body.day_of_month !== null) {
      if (
        !Number.isInteger(body.day_of_month) ||
        body.day_of_month < 1 ||
        body.day_of_month > 31
      ) {
        return errors
          .invalid('Day of month', 'must be an integer 1-31')
          .toResponse();
      }
    }

    // Validate project_id if provided
    if (body.project_id) {
      const projectIdResult = validateId(body.project_id, 'Project ID');
      if (!projectIdResult.valid) {
        return projectIdResult.error.toResponse();
      }

      // Verify project exists and belongs to user
      const project = await TodoDB.getProjectById(
        projectIdResult.value,
        session.user_id
      );
      if (!project) {
        return errors.projectNotFound().toResponse();
      }
    }

    // Validate priority if provided
    if (body.priority) {
      const validPriorities = ['low', 'medium', 'high', 'urgent'];
      if (!validPriorities.includes(body.priority)) {
        return errors
          .invalid('Priority', `must be one of: ${validPriorities.join(', ')}`)
          .toResponse();
      }
    }

    // Create the recurring task
    const recurringTask = await TodoDB.createRecurringTask(session.user_id, {
      title: titleResult.value,
      frequency: body.frequency,
      start_date: body.start_date,
      interval_value: body.interval_value,
      weekdays: body.weekdays,
      day_of_month: body.day_of_month,
      end_date: body.end_date,
      project_id: body.project_id,
      description: body.description,
      priority: body.priority,
      estimated_hours: body.estimated_hours,
      tags: body.tags,
      context: body.context,
      skip_missed: body.skip_missed,
    });

    return createdResponse(recurringTask);
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
