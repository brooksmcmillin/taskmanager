import { TodoDB } from '../../../../lib/db.js';
import { requireAuth } from '../../../../lib/auth.js';

export const POST = async ({ params, request }) => {
  const session = await requireAuth(request);
  const { id } = params;

  if (!id) {
    return new Response(
      JSON.stringify({ error: 'Missing id' }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  await TodoDB.completeTodo(
    parseInt(id),
    session.user_id,
  );
  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
