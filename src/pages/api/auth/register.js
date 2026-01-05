import { Auth } from '../../../lib/auth.js';

function validatePassword(password) {
  if (password.length < 12) {
    return 'Password must be at least 12 characters';
  }
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }
  if (!/[0-9]/.test(password)) {
    return 'Password must contain at least one number';
  }
  if (!/[^a-zA-Z0-9]/.test(password)) {
    return 'Password must contain at least one special character';
  }
  return null;
}

export async function POST({ request }) {
  // Disable Registration for now
  return new Response(
    JSON.stringify({ error: 'Registration is currently disabled' }),
    {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    }
  );

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

    // Validate password strength
    const passwordError = validatePassword(password);
    if (passwordError) {
      return new Response(JSON.stringify({ error: passwordError }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      });
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
