import { TodoDB } from '../../../lib/db.js';
import { requireAuth } from '../../../lib/auth.js';

export const GET = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);

  if (!projectId) {
    return new Response(JSON.stringify({ error: 'Invalid project ID' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  const project = await TodoDB.getProjectById(projectId, session.user_id);

  if (!project) {
    return new Response(JSON.stringify({ error: 'Project not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  return new Response(JSON.stringify(project), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

export const PUT = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);
  const updates = await request.json();

  if (!projectId) {
    return new Response(JSON.stringify({ error: 'Invalid project ID' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  await TodoDB.updateProject(projectId, session.user_id, updates);

  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};

export const DELETE = async ({ params, request }) => {
  const session = await requireAuth(request);
  const projectId = parseInt(params.id);

  if (!projectId) {
    return new Response(JSON.stringify({ error: 'Invalid project ID' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Check if project exists and belongs to user
  const project = await TodoDB.getProjectById(projectId, session.user_id);
  if (!project) {
    return new Response(JSON.stringify({ error: 'Project not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  await TodoDB.deleteProject(projectId);

  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
};
