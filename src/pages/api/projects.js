import { TodoDB } from '../../lib/db.js';

export const GET = async () => {
  try {
    const projects = TodoDB.getProjects();
    return new Response(JSON.stringify(projects), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};

export const POST = async ({ request }) => {
  try {
    const body = await request.json();
    const result = TodoDB.createProject(body.name, body.description, body.color);
    return new Response(JSON.stringify({ id: result.lastInsertRowid }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
