import { TodoDB } from '../../../../lib/db.js';
import { Auth } from '../../../../lib/auth.js';

/**
 * OAuth 2.0 Device Authorization - User Consent Endpoint
 *
 * This endpoint handles the user's authorization decision for the device flow.
 * It is called when the user approves or denies the device authorization request.
 *
 * POST /api/oauth/device/authorize
 * Content-Type: application/x-www-form-urlencoded
 *
 * Parameters:
 * - user_code (required): The user code entered by the user
 * - action (required): 'allow' or 'deny'
 */

export async function POST({ request, redirect }) {
  try {
    console.log('[OAuth/Device/Authorize] POST request received');

    // Get authenticated user from session
    const sessionId = await Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      console.log('[OAuth/Device/Authorize] User not authenticated');
      return redirect('/login');
    }

    const userId = session.user_id;
    console.log('[OAuth/Device/Authorize] User authenticated:', session.username);

    const formData = await request.formData();
    const userCode = formData.get('user_code');
    const action = formData.get('action');

    console.log('[OAuth/Device/Authorize] Request params:', {
      user_code: userCode,
      action: action,
    });

    if (!userCode) {
      console.log('[OAuth/Device/Authorize] Missing user_code');
      return redirect('/oauth/device?error=missing_code');
    }

    if (!action || (action !== 'allow' && action !== 'deny')) {
      console.log('[OAuth/Device/Authorize] Invalid action:', action);
      return redirect(`/oauth/device?user_code=${encodeURIComponent(userCode)}&error=invalid_action`);
    }

    if (action === 'allow') {
      // Authorize the device
      const result = await TodoDB.authorizeDeviceCode(userCode, userId);

      if (!result) {
        console.log('[OAuth/Device/Authorize] Failed to authorize - code not found or expired');
        return redirect('/oauth/device?error=expired_code');
      }

      console.log('[OAuth/Device/Authorize] Device authorized successfully');

      // Redirect to success page
      return new Response(null, {
        status: 302,
        headers: {
          Location: '/oauth/device/success',
        },
      });
    } else {
      // Deny the device
      const result = await TodoDB.denyDeviceCode(userCode);

      if (!result) {
        console.log('[OAuth/Device/Authorize] Failed to deny - code not found or expired');
        return redirect('/oauth/device?error=expired_code');
      }

      console.log('[OAuth/Device/Authorize] Device authorization denied');

      // Redirect to denied page
      return new Response(null, {
        status: 302,
        headers: {
          Location: '/oauth/device/denied',
        },
      });
    }
  } catch (error) {
    console.error('[OAuth/Device/Authorize] POST error:', error);
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
