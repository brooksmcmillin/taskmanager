import { defineMiddleware } from 'astro:middleware';
import { Auth } from './lib/auth.js';
import { TodoDB } from './lib/db.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { request, url, redirect } = context;

  // OAuth endpoints that require Bearer token authentication
  const oauthProtectedRoutes = ['/api/oauth/userinfo'];
  const isOAuthProtectedRoute = oauthProtectedRoutes.some((route) => url.pathname.startsWith(route));

  // Routes that don't require authentication
  const unprotectedRoutes = [
    '/login',
    '/register',
    '/api/auth/login',
    '/api/auth/register',
    '/api/oauth/token',
    '/api/oauth/authorize',  // Users authorize BEFORE they have tokens
    '/oauth/authorize',      // Consent page
    '/src/styles/global.css',
  ];
  const isUnprotectedRoute = unprotectedRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

  console.log('[Middleware] Request to:', url.pathname, '- Protected:', isOAuthProtectedRoute, '- Unprotected:', isUnprotectedRoute);

  // Handle OAuth-protected API routes (require Bearer token)
  if (isOAuthProtectedRoute) {
    const oauthUser = await getOAuthUser(request);
    if (!oauthUser) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    context.locals.user = oauthUser;
  } else if (!isUnprotectedRoute) {
    const user = await getUser(request);
    if (!user) {
      console.log('[Middleware] User not authenticated, redirecting to login with return_to:', url.pathname + url.search);
      const loginUrl = new URL('/login', url.origin);
      loginUrl.searchParams.set('return_to', url.pathname + url.search);
      return redirect(loginUrl.toString());
    }

    context.locals.user = user;
  }

  const response = await next();

  // Set security headers on the response
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('X-XSS-Protection', '1; mode=block');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set(
    'Permissions-Policy',
    'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
  );

  // Remove potentially dangerous headers
  response.headers.delete('X-Powered-By');

  // HSTS (only in production)
  if (process.env.NODE_ENV === 'production') {
    response.headers.set(
      'Strict-Transport-Security',
      'max-age=31536000; includeSubDomains; preload'
    );
  }

  return response;
});

export async function getUser(request) {
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);

  if (!session) {
    return null;
  }

  return {
    id: session.user_id,
    username: session.username,
    email: session.email,
  };
}

export async function getOAuthUser(request) {
  const authHeader = request.headers.get('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }

  const token = authHeader.substring(7);

  try {
    const tokenData = await TodoDB.getAccessToken(token);

    if (!tokenData) {
      return null;
    }

    return {
      id: tokenData.user_id,
      username: tokenData.username,
      email: tokenData.email || null,
      scopes: JSON.parse(tokenData.scopes || '[]'),
      clientId: tokenData.client_id,
    };
  } catch (error) {
    console.error('OAuth token validation error:', error);
    return null;
  }
}
