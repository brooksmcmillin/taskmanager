import { Auth } from '../../../lib/auth.js';
import { loginRateLimiter } from '../../../lib/rateLimit.js';

export async function POST({ request }) {
  try {
    // Get client IP for rate limiting
    const clientIp = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
      || request.headers.get('x-real-ip')
      || 'unknown';

    // Check rate limit before processing
    const rateLimitCheck = loginRateLimiter.check(clientIp, 5, 15 * 60 * 1000);
    if (!rateLimitCheck.allowed) {
      return new Response(
        JSON.stringify({
          error: 'Too many login attempts. Please try again later.',
          retryAfter: rateLimitCheck.retryAfter
        }),
        {
          status: 429,
          headers: {
            'Content-Type': 'application/json',
            'Retry-After': String(rateLimitCheck.retryAfter)
          },
        }
      );
    }

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

    // Record attempt before authentication
    loginRateLimiter.recordAttempt(clientIp);

    const user = await Auth.authenticateUser(username, password);

    // Clear rate limit on successful login
    loginRateLimiter.clearAttempts(clientIp);

    const session = await Auth.createSession(user.id);

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
    return new Response(JSON.stringify({ error: 'Invalid credentials' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
