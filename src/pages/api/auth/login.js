import { Auth } from '../../../lib/auth.js';

export async function POST({ request }) {
  console.log('In Post');
  try {
    const { username, password } = await request.json();

    if (!username || !password) {
      return new Response(
        JSON.stringify({ error: 'Username and password required' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const user = await Auth.authenticateUser(username, password);
    console.log('Got User?: ' + user);
    const session = await Auth.createSession(user.id);

    console.log(
      'LoginSession: ' + session.sessionId + ':' + typeof session.sessionId
    );

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
    console.log('Error: ' + error.message);
    return new Response(JSON.stringify({ error: error.message }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
