import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';
import {
  successResponse,
  errorResponse,
  notFoundResponse,
} from '../../../lib/apiResponse.js';

export const GET = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);

  if (!projectId) {
    return errorResponse('Invalid project ID');
  }

  const project = await TodoDB.getProjectById(projectId, session.user_id);

  if (!project) {
    return notFoundResponse('Project not found');
  }

  return successResponse(project);
};

export const PUT = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);
  const updates = await request.json();

  if (!projectId) {
    return errorResponse('Invalid project ID');
  }

  await TodoDB.updateProject(projectId, session.user_id, updates);

  return successResponse({ success: true });
};

export const DELETE = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);

  if (!projectId) {
    return errorResponse('Invalid project ID');
  }

  // Check if project exists and belongs to user
  const project = await TodoDB.getProjectById(projectId, session.user_id);
  if (!project) {
    return notFoundResponse('Project not found');
  }

  await TodoDB.deleteProject(projectId, session.user_id);

  return successResponse({ success: true });
};
