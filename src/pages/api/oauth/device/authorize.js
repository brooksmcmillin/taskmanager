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
    // Get authenticated user from session
    const sessionId = await Auth.getSessionFromRequest(request);
    const session = await Auth.getSessionUser(sessionId);

    if (!session) {
      return redirect('/login');
    }

    const userId = session.user_id;

    const formData = await request.formData();
    const userCode = formData.get('user_code');
    const action = formData.get('action');

    if (!userCode) {
      return redirect('/oauth/device?error=missing_code');
    }

    if (!action || (action !== 'allow' && action !== 'deny')) {
      return redirect(`/oauth/device?user_code=${encodeURIComponent(userCode)}&error=invalid_action`);
    }

    if (action === 'allow') {
      // Authorize the device
      const result = await TodoDB.authorizeDeviceCode(userCode, userId);

      if (!result) {
        return redirect('/oauth/device?error=expired_code');
      }

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
        return redirect('/oauth/device?error=expired_code');
      }

      // Redirect to denied page
      return new Response(null, {
        status: 302,
        headers: {
          Location: '/oauth/device/denied',
        },
      });
    }
  } catch (error) {
    console.error('[OAuth/Device/Authorize] Error:', error.message);
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
