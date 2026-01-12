import { TodoDB } from '../../../lib/db.js';
import { Auth } from '../../../lib/auth.js';

export async function GET({ request, redirect, url }) {
  const searchParams = url.searchParams;
  const clientId = searchParams.get('client_id');
  const redirectUri = searchParams.get('redirect_uri');
  const responseType = searchParams.get('response_type');
  const scope = searchParams.get('scope') || 'read';
  const state = searchParams.get('state');
  const codeChallenge = searchParams.get('code_challenge');
  const codeChallengeMethod = searchParams.get('code_challenge_method');

  // Validate required parameters
  if (!clientId || !redirectUri || responseType !== 'code') {
    return new Response('Invalid request parameters', { status: 400 });
  }

  try {
    // Validate OAuth client
    const client = await TodoDB.getOAuthClient(clientId);
    if (!client) {
      return new Response('Invalid client', { status: 400 });
    }

    // Validate redirect URI
    const allowedUris = JSON.parse(client.redirect_uris);
    if (!allowedUris.includes(redirectUri)) {
      return new Response('Invalid redirect URI', { status: 400 });
    }

    // Check if user is authenticated
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      // Redirect to login with return URL
      const returnTo = url.pathname + url.search;
      const loginUrl = new URL('/login', url.origin);
      loginUrl.searchParams.set('return_to', returnTo);
      return redirect(loginUrl.toString());
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    // Build consent page URL with parameters
    const consentUrl = new URL('/oauth/authorize', url.origin);
    consentUrl.searchParams.set('client_id', clientId);
    consentUrl.searchParams.set('redirect_uri', redirectUri);
    consentUrl.searchParams.set('response_type', responseType);
    consentUrl.searchParams.set('scope', scope);
    if (state) consentUrl.searchParams.set('state', state);
    if (codeChallenge)
      consentUrl.searchParams.set('code_challenge', codeChallenge);
    if (codeChallengeMethod)
      consentUrl.searchParams.set('code_challenge_method', codeChallengeMethod);

    return redirect(consentUrl.toString());
  } catch (error) {
    console.error('[OAuth/Authorize] Error:', error.message);
    return new Response('Server error', { status: 500 });
  }
}

export async function POST({ request, redirect, url }) {
  const formData = await request.formData();
  const clientId = formData.get('client_id');
  const redirectUri = formData.get('redirect_uri');
  const scope = formData.get('scope') || 'read';
  const state = formData.get('state');
  const codeChallenge = formData.get('code_challenge');
  const codeChallengeMethod = formData.get('code_challenge_method');
  const action = formData.get('action');

  try {
    // Check if user is authenticated
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return redirect('/login');
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    // Validate OAuth client
    const client = await TodoDB.getOAuthClient(clientId);
    if (!client) {
      return new Response('Invalid client', { status: 400 });
    }

    const callbackUrl = new URL(redirectUri);

    if (action === 'deny') {
      // User denied authorization
      callbackUrl.searchParams.set('error', 'access_denied');
      if (state) callbackUrl.searchParams.set('state', state);
      return redirect(callbackUrl.toString());
    }

    if (action === 'allow') {
      // User approved authorization - create authorization code
      const scopes = scope.split(' ');
      const authCode = await TodoDB.createAuthorizationCode(
        clientId,
        user.id,
        redirectUri,
        scopes,
        codeChallenge,
        codeChallengeMethod
      );

      callbackUrl.searchParams.set('code', authCode.code);
      if (state) callbackUrl.searchParams.set('state', state);

      return redirect(callbackUrl.toString());
    }

    return new Response('Invalid action', { status: 400 });
  } catch (error) {
    console.error('[OAuth/Authorize] Error:', error.message);
    return new Response('Server error', { status: 500 });
  }
}
