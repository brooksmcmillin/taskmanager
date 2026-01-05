import { TodoDB } from '../../../../lib/db.js';

/**
 * OAuth 2.0 Device Authorization Endpoint (RFC 8628)
 *
 * This endpoint initiates the device authorization flow by generating
 * a device code and user code that the CLI can display to the user.
 *
 * POST /api/oauth/device/code
 * Content-Type: application/x-www-form-urlencoded
 *
 * Parameters:
 * - client_id (required): The OAuth client ID
 * - scope (optional): Space-separated list of scopes (defaults to client's scopes)
 *
 * Response:
 * {
 *   "device_code": "...",           // Secret code for polling
 *   "user_code": "WDJB-MJHT",       // Code for user to enter
 *   "verification_uri": "...",       // URL for user to visit
 *   "verification_uri_complete": "...", // URL with code pre-filled
 *   "expires_in": 1800,              // Seconds until codes expire
 *   "interval": 5                    // Minimum polling interval in seconds
 * }
 */

export async function OPTIONS() {
  return new Response(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}

export async function POST({ request, url }) {
  try {
    console.log('[OAuth/Device/Code] POST request received');

    const formData = await request.formData();
    const clientId = formData.get('client_id');
    const requestedScope = formData.get('scope');

    console.log('[OAuth/Device/Code] Request params:', {
      client_id: clientId,
      scope: requestedScope,
    });

    // Validate client_id is provided
    if (!clientId) {
      console.log('[OAuth/Device/Code] Missing client_id');
      return new Response(
        JSON.stringify({
          error: 'invalid_request',
          error_description: 'client_id is required',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Get client (no secret validation for device flow initial request)
    const client = await TodoDB.getOAuthClient(clientId);
    if (!client) {
      console.log('[OAuth/Device/Code] Invalid client_id:', clientId);
      return new Response(
        JSON.stringify({
          error: 'invalid_client',
          error_description: 'Unknown client_id',
        }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    console.log('[OAuth/Device/Code] Client found:', client.name);

    // Validate that this client supports device_code grant
    const allowedGrantTypes = JSON.parse(client.grant_types || '[]');
    if (!allowedGrantTypes.includes('device_code')) {
      console.log(
        '[OAuth/Device/Code] Client not authorized for device_code grant'
      );
      return new Response(
        JSON.stringify({
          error: 'unauthorized_client',
          error_description: 'Client is not authorized to use device flow',
        }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    }

    // Determine scopes
    let scopes;
    const clientScopes = JSON.parse(client.scopes || '["read"]');

    if (requestedScope) {
      const requestedScopes = requestedScope.split(' ').filter(Boolean);

      // Validate requested scopes against client's allowed scopes
      const invalidScopes = requestedScopes.filter(
        (s) => !clientScopes.includes(s)
      );
      if (invalidScopes.length > 0) {
        console.log('[OAuth/Device/Code] Invalid scopes:', invalidScopes);
        return new Response(
          JSON.stringify({
            error: 'invalid_scope',
            error_description: `Invalid scope(s): ${invalidScopes.join(', ')}`,
          }),
          {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
      scopes = requestedScopes;
    } else {
      scopes = clientScopes;
    }

    console.log('[OAuth/Device/Code] Creating device authorization code');

    // Create device authorization code
    // Default expiry: 30 minutes (1800 seconds)
    // Default polling interval: 5 seconds
    const deviceAuth = await TodoDB.createDeviceAuthorizationCode(
      clientId,
      scopes,
      1800, // 30 minute expiry
      5 // 5 second polling interval
    );

    // Build verification URIs
    const baseUrl = `${url.protocol}//${url.host}`;
    const verificationUri = `${baseUrl}/oauth/device`;
    const verificationUriComplete = `${verificationUri}?user_code=${encodeURIComponent(deviceAuth.user_code)}`;

    console.log('[OAuth/Device/Code] Device code created:', {
      user_code: deviceAuth.user_code,
      verification_uri: verificationUri,
    });

    // Return RFC 8628 compliant response
    return new Response(
      JSON.stringify({
        device_code: deviceAuth.device_code,
        user_code: deviceAuth.user_code,
        verification_uri: verificationUri,
        verification_uri_complete: verificationUriComplete,
        expires_in: deviceAuth.expires_in,
        interval: deviceAuth.interval,
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'no-store',
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST, OPTIONS',
          'Access-Control-Allow-Headers': 'Content-Type',
        },
      }
    );
  } catch (error) {
    console.error('[OAuth/Device/Code] POST error:', error);
    return new Response(
      JSON.stringify({
        error: 'server_error',
        error_description: 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
