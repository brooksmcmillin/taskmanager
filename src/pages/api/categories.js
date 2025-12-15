import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';

export const GET = async ({ request }) => {
  const session = await requireAuth(request);

  const categories = await TodoDB.getCategoriesWithCounts(session.user_id);

  const formattedCategories = categories.map((cat) => ({
    name: cat.name,
    task_count: parseInt(cat.task_count, 10),
  }));

  return new Response(JSON.stringify({ categories: formattedCategories }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
