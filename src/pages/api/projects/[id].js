import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import { errors } from '../../../lib/errors.js';
import { validateId } from '../../../lib/validators.js';
import { apiResponse } from '../../../lib/apiResponse.js';

export const GET = async ({ params, request }) => {
  try {
    const session = await requireAuth(request);

    const idResult = validateId(params.id, 'Project ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const project = await TodoDB.getProjectById(idResult.value, session.user_id);

    if (!project) {
      return errors.notFound('Project').toResponse();
    }

    return apiResponse(project);
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

    const idResult = validateId(params.id, 'Project ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    const updates = await request.json();

    // Check if project exists and belongs to user
    const project = await TodoDB.getProjectById(idResult.value, session.user_id);
    if (!project) {
      return errors.notFound('Project').toResponse();
    }

    await TodoDB.updateProject(idResult.value, session.user_id, updates);

    return apiResponse({ updated: true });
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

    const idResult = validateId(params.id, 'Project ID');
    if (!idResult.valid) {
      return idResult.error.toResponse();
    }

    // Check if project exists and belongs to user
    const project = await TodoDB.getProjectById(idResult.value, session.user_id);
    if (!project) {
      return errors.notFound('Project').toResponse();
    }

    await TodoDB.deleteProject(idResult.value, session.user_id);

    return apiResponse({ deleted: true });
  } catch (error) {
    if (error.message === 'Authentication required') {
      return errors.authRequired().toResponse();
    }
    return errors.internal(error.message).toResponse();
  }
};
