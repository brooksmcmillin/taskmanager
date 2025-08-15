import { TodoDB } from '../../lib/db.js';
import { requireAuth } from '../../lib/auth.js';

export const GET = async ({ request }) => {
  const session = await requireAuth(request);
  const projects = await TodoDB.getProjects(session.user_id);
  return new Response(JSON.stringify(projects), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
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
  return new Response(JSON.stringify({ id: result.id }), {
    status: 201,
    headers: { 'Content-Type': 'application/json' },
  });
};
