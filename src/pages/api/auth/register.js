import { Auth } from '../../../lib/auth.js';

export async function POST({ request }) {

  // Disable Registration for now
  return new Response(JSON.stringify({ error: "Registration is currently disabled" }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });

  try {
    const { username, email, password } = await request.json();

    if (!username || !email || !password) {
      return new Response(
        JSON.stringify({ error: 'Missing required fields' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    if (password.length < 6) {
      return new Response(
        JSON.stringify({ error: 'Password must be at least 6 characters' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    const result = await Auth.createUser(username, email, password);

    return new Response(
      JSON.stringify({
        success: true,
        message: 'User created successfully',
        userId: result.id,
      }),
      {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
