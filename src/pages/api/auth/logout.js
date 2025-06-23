import { Auth } from '../../../lib/auth.js';

export async function POST({ request }) {
  try {
    const sessionId = await Auth.getSessionFromRequest(request);
    console.log("Logout Session: " + sessionId);
    
    if (sessionId) {
      await Auth.deleteSession(sessionId);
    }

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { 
        'Content-Type': 'application/json',
        'Set-Cookie': Auth.clearSessionCookie()
      }
    });

  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
