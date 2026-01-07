import { defineMiddleware } from 'astro:middleware';
import { Auth } from './lib/auth.js';
import { TodoDB } from './lib/db.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { request, url, redirect } = context;

  // CSRF Protection (replaces Astro's checkOrigin with OAuth exceptions)
  // OAuth endpoints are exempt because they use client credentials, not cookies
  const csrfExemptRoutes = [
    '/api/oauth/token',
    '/api/oauth/device/code',
    '/api/oauth/authorize',
  ];
  const isCSRFExempt = csrfExemptRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

  if (!isCSRFExempt && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(request.method)) {
    const origin = request.headers.get('origin');
    const host = request.headers.get('host');

    // Allow requests with no origin (same-origin, non-browser clients like curl)
    // But if origin IS present, it must match the host
    if (origin) {
      const originUrl = new URL(origin);
      const expectedHost = host?.split(':')[0]; // Remove port if present

      if (originUrl.host.split(':')[0] !== expectedHost) {
        return new Response(
          JSON.stringify({ error: 'CSRF validation failed: origin mismatch' }),
          { status: 403, headers: { 'Content-Type': 'application/json' } }
        );
      }
    }
  }

  // OAuth endpoints that require Bearer token authentication
  const oauthProtectedRoutes = ['/api/oauth/userinfo'];
  const isOAuthProtectedRoute = oauthProtectedRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

  // Routes that don't require authentication
  const unprotectedRoutes = [
    '/login',
    '/register',
    '/api/auth/login',
    '/api/auth/register',
    '/api/oauth/token',
    '/api/oauth/authorize', // Users authorize BEFORE they have tokens
    '/api/oauth/device/code', // Device flow: CLI requests device code
    '/oauth/authorize', // Consent page
    '/src/styles/global.css',
  ];
  // Note: /oauth/device requires authentication - middleware redirects to login
  const isUnprotectedRoute = unprotectedRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

  // Handle OAuth-protected API routes (require Bearer token)
  if (isOAuthProtectedRoute) {
    const oauthUser = await getOAuthUser(request);
    if (!oauthUser) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      });
    }
    context.locals.user = oauthUser;
  } else if (!isUnprotectedRoute) {
    const user = await getUser(request);
    if (!user) {
      const loginUrl = new URL('/login', url.origin);
      loginUrl.searchParams.set('return_to', url.pathname + url.search);
      return redirect(loginUrl.toString());
    }

    context.locals.user = user;
  }

  const response = await next();

  // Set cache control headers based on content type
  const contentType = response.headers.get('Content-Type') || '';
  const isAPI = url.pathname.startsWith('/api/');
  const isStaticAsset = url.pathname.startsWith('/_astro/') ||
                        url.pathname.match(/\.(js|css|woff2?|ttf|eot|ico|png|jpg|jpeg|gif|svg|webp)$/);

  if (isAPI) {
    // API responses should never be cached (contain user-specific data)
    response.headers.set('Cache-Control', 'no-store, no-cache, must-revalidate');
  } else if (isStaticAsset) {
    // Static assets with hashed filenames can be cached long-term
    response.headers.set('Cache-Control', 'public, max-age=31536000, immutable');
  } else if (contentType.includes('text/html')) {
    // HTML pages should revalidate to get fresh content
    response.headers.set('Cache-Control', 'no-cache, must-revalidate');
  }

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

  // Content Security Policy
  // NOTE: 'unsafe-inline' is required for Astro's inline scripts.
  // To remove it, implement CSP nonces:
  // 1. Generate nonce in middleware: crypto.randomBytes(16).toString('base64')
  // 2. Pass nonce via context.locals.cspNonce
  // 3. Add nonce={Astro.locals.cspNonce} to all <script> and <style> tags
  // 4. Update CSP: script-src 'self' 'nonce-{nonce}'
  response.headers.set(
    'Content-Security-Policy',
    "default-src 'self'; " +
      "script-src 'self' 'unsafe-inline'; " +
      "style-src 'self' 'unsafe-inline'; " +
      "img-src 'self' data: https:; " +
      "font-src 'self'; " +
      "connect-src 'self'; " +
      "frame-ancestors 'none'; " +
      "base-uri 'self'; " +
      "form-action 'self'; " +
      'upgrade-insecure-requests'
  );

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
  // First try Bearer token authentication (for OAuth2 access tokens)
  const authHeader = request.headers.get('Authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
    try {
      const tokenData = await TodoDB.getAccessToken(token);
      if (tokenData) {
        return {
          id: tokenData.user_id,
          username: tokenData.username,
          email: tokenData.email || null,
          auth_type: 'bearer',
        };
      }
    } catch (error) {
      console.error('[Middleware] Bearer token validation error:', error);
    }
  }

  // Fall back to session-based authentication
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);

  if (!session) {
    return null;
  }

  return {
    id: session.user_id,
    username: session.username,
    email: session.email,
    auth_type: 'session',
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
