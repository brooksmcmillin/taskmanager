import { TodoDB } from '../../../../lib/db.js';

export const POST = async ({ params, request }) => {
  try {
    const { id } = params;
    const { actual_hours } = await request.json();
    
    if (!id || !actual_hours) {
      return new Response(JSON.stringify({ error: 'Missing id or actual_hours' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    TodoDB.completeTodo(parseInt(id), parseFloat(actual_hours));
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  } catch (error) {
    console.error('Error completing todo:', error);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
};
