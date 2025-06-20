import { TodoDB } from '../../lib/db.js';

export const GET = async ({ url }) => {
  try {
    const searchParams = new URL(url).searchParams;
    const projectId = searchParams.get('project_id');
    const status = searchParams.get('status');
    
    const todos = TodoDB.getTodos(projectId, status);
    return new Response(JSON.stringify(todos), {
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
    const result = TodoDB.createTodo(body);
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

export const PUT = async ({ request }) => {
  try {
    const body = await request.json();
    const { id, ...updates } = body;
    TodoDB.updateTodo(id, updates);
    return new Response(JSON.stringify({ success: true }), {
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
