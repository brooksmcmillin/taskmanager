import { Auth } from '../../../lib/auth.js';

export async function POST({ request }) {
  console.log('[Auth/Login] POST request received');
  try {
    const { username, password } = await request.json();

    console.log('[Auth/Login] Login attempt for username:', username);

    if (!username || !password) {
      console.log('[Auth/Login] Missing credentials');
      return new Response(
        JSON.stringify({ error: 'Username and password required' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const user = await Auth.authenticateUser(username, password);
    console.log('[Auth/Login] User authenticated:', user.username);

    const session = await Auth.createSession(user.id);
    console.log('[Auth/Login] Session created:', session.sessionId);

    return new Response(
      JSON.stringify({
        success: true,
        user: {
          id: user.id,
          username: user.username,
          email: user.email,
        },
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Set-Cookie': Auth.createSessionCookie(
            session.sessionId,
            session.expiresAt
          ),
        },
      }
    );
  } catch (error) {
    console.error('[Auth/Login] Authentication failed:', error.message);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
