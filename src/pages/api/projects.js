import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';
import { errors } from '../../lib/errors.js';
import { validateRequired } from '../../lib/validators.js';
import { successResponse, createdResponse } from '../../lib/apiResponse.js';

export const GET = async ({ request }) => {
  try {
    const session = await requireAuth(request);
    const projects = await TodoDB.getProjects(session.user_id);
    // Return raw array for frontend compatibility
    return successResponse(projects);
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
    const nameResult = validateRequired(body.name, 'Project name');
    if (!nameResult.valid) {
      return nameResult.error.toResponse();
    }

    const result = await TodoDB.createProject(
      session.user_id,
      nameResult.value,
      body.description,
      body.color
    );
    return createdResponse({ id: result.id, name: nameResult.value });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
