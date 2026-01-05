import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';
import { successResponse, createdResponse } from '../../lib/apiResponse.js';

export const GET = async ({ request }) => {
  const session = await requireAuth(request);
  const projects = await TodoDB.getProjects(session.user_id);
  return successResponse(projects);
};

export const POST = async ({ request }) => {
  const session = await requireAuth(request);
  const body = await request.json();
  const result = await TodoDB.createProject(
    session.user_id,
    body.name,
    body.description,
    body.color
  );
  return createdResponse({ id: result.id });
};
