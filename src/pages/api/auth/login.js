import { Auth } from '../../../lib/auth.js';
import { loginRateLimiter } from '../../../lib/rateLimit.js';
import { config } from '../../../lib/config.js';
import { errors } from '../../../lib/errors.js';
import { validateRequired } from '../../../lib/validators.js';
import { apiResponse, rateLimitResponse } from '../../../lib/apiResponse.js';

export async function POST({ request }) {
  try {
    // Get client IP for rate limiting
    const clientIp =
      request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ||
      request.headers.get('x-real-ip') ||
      'unknown';

    // Check rate limit before processing
    const rateLimitCheck = loginRateLimiter.check(
      clientIp,
      config.auth.maxLoginAttempts,
      config.auth.rateLimitWindowMs
    );
    if (!rateLimitCheck.allowed) {
      return rateLimitResponse(rateLimitCheck.retryAfter);
    }

    const body = await request.json();

    // Validate required fields
    const usernameResult = validateRequired(body.username, 'Username');
    if (!usernameResult.valid) {
      return usernameResult.error.toResponse();
    }

    const passwordResult = validateRequired(body.password, 'Password');
    if (!passwordResult.valid) {
      return passwordResult.error.toResponse();
    }

    // Record attempt before authentication
    loginRateLimiter.recordAttempt(clientIp);

    const user = await Auth.authenticateUser(usernameResult.value, passwordResult.value);

    // Clear rate limit on successful login
    loginRateLimiter.clearAttempts(clientIp);

    const session = await Auth.createSession(user.id);

    return new Response(
      JSON.stringify({
        data: {
          user: {
            id: user.id,
            username: user.username,
            email: user.email,
          },
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
    return errors.invalidCredentials().toResponse();
  }
}
