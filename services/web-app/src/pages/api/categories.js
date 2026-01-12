import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';
import { successResponse } from '../../lib/apiResponse.js';

export const GET = async ({ request }) => {
  const session = await requireAuth(request);

  const categories = await TodoDB.getCategoriesWithCounts(session.user_id);

  const formattedCategories = categories.map((cat) => ({
    name: cat.name,
    task_count: parseInt(cat.task_count, 10),
  }));

  return successResponse({ categories: formattedCategories });
};
