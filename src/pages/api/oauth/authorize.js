import { TodoDB } from '../../../lib/db.js';
import { Auth } from '../../../lib/auth.js';
import crypto from 'crypto';

export async function GET({ request, redirect, url }) {
  console.error('=== [OAuth/Authorize API] GET REQUEST STARTED ===');
  console.log('[OAuth/Authorize] GET request received');
  const searchParams = url.searchParams;
  const clientId = searchParams.get('client_id');
  const redirectUri = searchParams.get('redirect_uri');
  const responseType = searchParams.get('response_type');
  const scope = searchParams.get('scope') || 'read';
  const state = searchParams.get('state');
  const codeChallenge = searchParams.get('code_challenge');
  const codeChallengeMethod = searchParams.get('code_challenge_method');

  console.log('[OAuth/Authorize] Request params:', {
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: responseType,
    scope,
    has_state: !!state,
    has_code_challenge: !!codeChallenge,
    code_challenge_method: codeChallengeMethod,
  });

  // Validate required parameters
  if (!clientId || !redirectUri || responseType !== 'code') {
    console.log(
      '[OAuth/Authorize] GET validation failed - missing required params'
    );
    return new Response('Invalid request parameters', { status: 400 });
  }

  try {
    // Validate OAuth client
    const client = await TodoDB.getOAuthClient(clientId);
    if (!client) {
      console.log(
        '[OAuth/Authorize] GET failed - invalid client_id:',
        clientId
      );
      return new Response('Invalid client', { status: 400 });
    }

    console.log('[OAuth/Authorize] Client validated:', client.name);

    // Validate redirect URI
    const allowedUris = JSON.parse(client.redirect_uris);
    if (!allowedUris.includes(redirectUri)) {
      console.log(
        '[OAuth/Authorize] GET failed - invalid redirect_uri:',
        redirectUri
      );
      console.log('[OAuth/Authorize] Allowed URIs:', allowedUris);
      return new Response('Invalid redirect URI', { status: 400 });
    }

    console.log('[OAuth/Authorize] Redirect URI validated');

    // Check if user is authenticated
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log(
        '[OAuth/Authorize] User not authenticated, redirecting to login'
      );
      // Redirect to login with return URL
      const returnTo = url.pathname + url.search;
      console.log('[OAuth/Authorize] return_to value:', returnTo);
      const loginUrl = new URL('/login', url.origin);
      loginUrl.searchParams.set('return_to', returnTo);
      console.log('[OAuth/Authorize] Full login URL:', loginUrl.toString());
      return redirect(loginUrl.toString());
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    console.log('[OAuth/Authorize] User authenticated:', user.username);

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

    console.log('[OAuth/Authorize] Redirecting to consent page');
    return redirect(consentUrl.toString());
  } catch (error) {
    console.error('[OAuth/Authorize] GET error:', error);
    return new Response('Server error', { status: 500 });
  }
}

export async function POST({ request, redirect, url }) {
  console.log('[OAuth/Authorize] POST request received');
  const formData = await request.formData();
  const clientId = formData.get('client_id');
  const redirectUri = formData.get('redirect_uri');
  const scope = formData.get('scope') || 'read';
  const state = formData.get('state');
  const codeChallenge = formData.get('code_challenge');
  const codeChallengeMethod = formData.get('code_challenge_method');
  const action = formData.get('action');

  console.log('[OAuth/Authorize] POST params:', {
    client_id: clientId,
    redirect_uri: redirectUri,
    scope,
    action,
    has_state: !!state,
    has_code_challenge: !!codeChallenge,
  });

  try {
    // Check if user is authenticated
    const sessionId = Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Authorize] POST unauthorized - no valid session');
      return redirect('/login');
    }

    const user = {
      id: session.user_id,
      username: session.username,
      email: session.email,
    };

    console.log('[OAuth/Authorize] POST authorized for user:', user.username);

    // Validate OAuth client
    const client = await TodoDB.getOAuthClient(clientId);
    if (!client) {
      console.log(
        '[OAuth/Authorize] POST failed - invalid client_id:',
        clientId
      );
      return new Response('Invalid client', { status: 400 });
    }

    console.log('[OAuth/Authorize] Client validated:', client.name);

    const callbackUrl = new URL(redirectUri);

    if (action === 'deny') {
      console.log('[OAuth/Authorize] User denied authorization');
      // User denied authorization
      callbackUrl.searchParams.set('error', 'access_denied');
      if (state) callbackUrl.searchParams.set('state', state);
      return redirect(callbackUrl.toString());
    }

    if (action === 'allow') {
      console.log(
        '[OAuth/Authorize] User approved authorization, creating auth code'
      );
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

      console.log(
        '[OAuth/Authorize] Authorization code created:',
        authCode.code
      );

      callbackUrl.searchParams.set('code', authCode.code);
      if (state) callbackUrl.searchParams.set('state', state);

      console.log('[OAuth/Authorize] Redirecting to:', redirectUri);
      return redirect(callbackUrl.toString());
    }

    console.log('[OAuth/Authorize] POST failed - invalid action:', action);
    return new Response('Invalid action', { status: 400 });
  } catch (error) {
    console.error('[OAuth/Authorize] POST error:', error);
    return new Response('Server error', { status: 500 });
  }
}
