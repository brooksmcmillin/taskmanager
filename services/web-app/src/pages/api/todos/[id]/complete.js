import { TodoDB } from '../../../../lib/db.js';
import { requireAuth } from '../../../../lib/auth.js';
import { successResponse, errorResponse } from '../../../../lib/apiResponse.js';

export const POST = async ({ params, request }) => {
  const session = await requireAuth(request);
  const { id } = params;

  if (!id) {
    return errorResponse('Missing id');
  }

  await TodoDB.completeTodo(parseInt(id), session.user_id);
  return successResponse({ success: true });
};
