import { TodoDB } from '../../lib/db.js';
import { Auth } from '../../lib/auth.js';

async function requireAuth(request) {
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);

  if (!session) {
    throw new Error('Authentication required');
  }

  return session;
}

export const GET = async ({ url, request }) => {
  try {
    const session = await requireAuth(request);
    const searchParams = new URL(url).searchParams;

    const startDate = searchParams.get('start_date');
    const endDate = searchParams.get('end_date');
    const status = searchParams.get('status') || 'all';
    const timeHorizon = searchParams.get('time_horizon');

    if (!startDate || !endDate) {
      return new Response(
        JSON.stringify({ error: 'start_date and end_date are required' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Get todos for the date range
    const todos = await TodoDB.getTodosForDateRange(
      session.user_id,
      startDate,
      endDate,
      timeHorizon,
      status === 'all' ? null : status
    );

    // Get all user projects for reference
    const projects = await TodoDB.getProjects(session.user_id);

    return new Response(
      JSON.stringify({
        todos,
        projects,
        dateRange: { startDate, endDate },
        status,
      }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    const status = error.message === 'Authentication required' ? 401 : 500;
    return new Response(JSON.stringify({ error: error.message }), {
      status,
      headers: { 'Content-Type': 'application/json' },
    });
  }
};
