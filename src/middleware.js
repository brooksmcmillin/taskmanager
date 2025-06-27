import { defineMiddleware } from 'astro:middleware';
import { Auth } from './lib/auth.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { request, url, redirect } = context;

  const unprotectedRoutes = [
    '/login',
    '/api/auth/login',
    '/src/styles/global.css',
  ];
  const isUnprotectedRoute = unprotectedRoutes.some((route) =>
    url.pathname.startsWith(route)
  );

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
