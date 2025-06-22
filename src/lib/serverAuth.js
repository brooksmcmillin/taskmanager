import { Auth } from './auth.js';
import { APIRoute } from 'astro';

export function checkAuth(request) {
  const sessionId = Auth.getSessionFromRequest(request);
  const session = Auth.getSessionUser(sessionId);

  console.log("Session: " + session);
  
  if (!session) {
    return { 
      user: null, 
      redirect: Astro.redirect("/login")
    };
  }
  
  return { 
    user: { 
      id: session.user_id, 
      username: session.username, 
      email: session.email 
    }, 
    redirect: null 
  };
}

export function requireAuth(request) {
  const auth = checkAuth(request);
  console.log("Auth: " + auth);
  if (auth.redirect) {
    return auth.redirect;
  }
  return auth.user;
}
