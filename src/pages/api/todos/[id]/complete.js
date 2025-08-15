import { TodoDB } from '../../../../lib/db.js';
import { requireAuth } from '../../../../lib/auth.js';

export const POST = async ({ params, request }) => {
  const session = await requireAuth(request);
  const { id } = params;
  const { actual_hours } = await request.json();

  if (!id || !actual_hours) {
    return new Response(
      JSON.stringify({ error: 'Missing id or actual_hours' }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  await TodoDB.completeTodo(
    parseInt(id),
    session.user_id,
    parseFloat(actual_hours)
  );
  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
