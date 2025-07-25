import { defineMiddleware } from 'astro:middleware';
import { Auth } from './lib/auth.js';
import { TodoDB } from './lib/db.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { request, url, redirect } = context;

  // Security headers
  context.response.headers.set('X-Content-Type-Options', 'nosniff');
  context.response.headers.set('X-Frame-Options', 'DENY');
  context.response.headers.set('X-XSS-Protection', '1; mode=block');
  context.response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  context.response.headers.set('Permissions-Policy', 
    'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
  );
  
  // Remove potentially dangerous headers
  context.response.headers.delete('X-Powered-By');
  
  // HSTS (only in production)
  if (process.env.NODE_ENV === 'production') {
    context.response.headers.set('Strict-Transport-Security', 
      'max-age=31536000; includeSubDomains; preload'
    );
  }
 
  // OAuth endpoints should allow cross-origin requests
  const oauthRoutes = ['/api/oauth/token', '/api/oauth/authorize'];
  const isOAuthRoute = oauthRoutes.some(route => url.pathname === route);
  
  // Skip origin checking for OAuth endpoints
  if (!isOAuthRoute) {
    // Add your origin validation logic here for non-OAuth routes
    // This ensures only OAuth endpoints bypass origin checking
  }

  const unprotectedRoutes = [
    '/login',
    '/api/auth/login',
    '/api/oauth/token',
    '/src/styles/global.css',
  ];
  const isUnprotectedRoute = unprotectedRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

  // Handle OAuth-protected API routes
  if (url.pathname.startsWith('/api/') && !isUnprotectedRoute && !url.pathname.startsWith('/api/auth/') && !url.pathname.startsWith('/api/oauth/')) {
    const oauthUser = await getOAuthUser(request);
    if (oauthUser) {
      context.locals.user = oauthUser;
      return next();
    }
  }

  if (!isUnprotectedRoute) {
    const user = await getUser(request);

    if (!user) {
      return redirect('/login');
    }

    context.locals.user = user;
  }

  return next();
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
      clientId: tokenData.client_id
    };
  } catch (error) {
    console.error('OAuth token validation error:', error);
    return null;
  }
}
