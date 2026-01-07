/**
 * API Response utilities for consistent JSON responses
 *
 * Standard Response Format:
 * - Success: { data: <payload>, meta?: { count, page, etc. } }
 * - Error: { error: { code: string, message: string, details?: object } }
 */

import { config } from './config.js';

// =============================================================================
// Constants
// =============================================================================

const JSON_HEADERS = { 'Content-Type': 'application/json' };

const OAUTH_HEADERS = {
  'Content-Type': 'application/json',
  'Cache-Control': 'no-store',
};

// =============================================================================
// CORS Handling
// =============================================================================

/**
 * Get CORS headers for a request, validating the origin.
 * @param {Request} request - The incoming request
 * @returns {Object} CORS headers object
 */
export function getCorsHeaders(request) {
  const origin = request.headers.get('origin');

  // If no origin (same-origin request or non-browser client), allow
  if (!origin) {
    return {
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };
  }

  // Check if origin is in allowed list
  if (config.cors.allowedOrigins.includes(origin)) {
    return {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      'Access-Control-Allow-Credentials': 'true',
      Vary: 'Origin',
    };
  }

  // Origin not allowed - return minimal CORS headers (browser will block)
  return {
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}

/**
 * Create a CORS preflight response (for OPTIONS requests)
 * @param {Request} request - The incoming request
 * @returns {Response}
 */
export function corsPreflightResponse(request) {
  return new Response(null, {
    status: 204,
    headers: getCorsHeaders(request),
  });
}

// =============================================================================
// Standard Response Builders
// =============================================================================

/**
 * Create a raw JSON response (for backwards compatibility)
 * @param {any} data - Response data
 * @param {number} status - HTTP status code (default: 200)
 * @param {Object} [headers] - Additional headers
 * @returns {Response}
 */
export function jsonResponse(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...headers },
  });
}

/**
 * Create a standardized success response with envelope
 * @param {any} data - Response payload
 * @param {Object} [meta] - Optional metadata (count, pagination, etc.)
 * @returns {Response}
 */
export function apiResponse(data, meta = null) {
  const body = { data };
  if (meta) {
    body.meta = meta;
  }
  return jsonResponse(body, 200);
}

/**
 * Create a success response (backwards compatible - returns data directly)
 * @param {any} data - Response data
 * @returns {Response}
 * @deprecated Use apiResponse() for new endpoints
 */
export function successResponse(data) {
  return jsonResponse(data, 200);
}

/**
 * Create a created response (201) with standardized envelope
 * @param {any} data - Created resource data
 * @returns {Response}
 */
export function createdResponse(data) {
  return jsonResponse({ data }, 201);
}

/**
 * Create a no content response (204)
 * @returns {Response}
 */
export function noContentResponse() {
  return new Response(null, { status: 204 });
}

/**
 * Create a paginated response
 * @param {Array} items - Array of items
 * @param {Object} pagination - Pagination info
 * @param {number} pagination.page - Current page
 * @param {number} pagination.limit - Items per page
 * @param {number} pagination.total - Total items
 * @returns {Response}
 */
export function paginatedResponse(items, { page, limit, total }) {
  return jsonResponse({
    data: items,
    meta: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit),
      hasMore: page * limit < total,
    },
  }, 200);
}

// =============================================================================
// Error Response Builders
// =============================================================================

/**
 * Create an error response with standardized format
 * @param {string} code - Error code
 * @param {string} message - Error message
 * @param {number} status - HTTP status code (default: 400)
 * @param {Object} [details] - Additional error details
 * @returns {Response}
 */
export function apiErrorResponse(code, message, status = 400, details = null) {
  const body = {
    error: {
      code,
      message,
    },
  };
  if (details) {
    body.error.details = details;
  }
  return jsonResponse(body, status);
}

/**
 * Create an error response (backwards compatible - simple format)
 * @param {string} message - Error message
 * @param {number} status - HTTP status code (default: 400)
 * @returns {Response}
 * @deprecated Use apiErrorResponse() or errors.* for new endpoints
 */
export function errorResponse(message, status = 400) {
  return jsonResponse({ error: message }, status);
}

/**
 * Create a 401 unauthorized response
 * @param {string} message - Error message (default: 'Authentication required')
 * @returns {Response}
 */
export function unauthorizedResponse(message = 'Authentication required') {
  return apiErrorResponse('AUTH_002', message, 401);
}

/**
 * Create a 403 forbidden response
 * @param {string} message - Error message (default: 'Access denied')
 * @returns {Response}
 */
export function forbiddenResponse(message = 'Access denied') {
  return apiErrorResponse('AUTHZ_001', message, 403);
}

/**
 * Create a 404 not found response
 * @param {string} resource - Resource name (default: 'Resource')
 * @returns {Response}
 */
export function notFoundResponse(resource = 'Resource') {
  return apiErrorResponse('NOT_FOUND_001', `${resource} not found`, 404);
}

/**
 * Create a 409 conflict response
 * @param {string} message - Error message
 * @returns {Response}
 */
export function conflictResponse(message) {
  return apiErrorResponse('CONFLICT_001', message, 409);
}

/**
 * Create a 429 rate limit response
 * @param {number} [retryAfter] - Seconds until retry is allowed
 * @returns {Response}
 */
export function rateLimitResponse(retryAfter = null) {
  const headers = { ...JSON_HEADERS };
  if (retryAfter) {
    headers['Retry-After'] = String(retryAfter);
  }
  return new Response(
    JSON.stringify({
      error: {
        code: 'RATE_001',
        message: 'Too many requests. Please try again later.',
        ...(retryAfter && { details: { retryAfter } }),
      },
    }),
    { status: 429, headers }
  );
}

/**
 * Create a 500 internal server error response
 * @param {string} [message] - Error message (default: generic message)
 * @returns {Response}
 */
export function serverErrorResponse(message = 'An unexpected error occurred') {
  return apiErrorResponse('SERVER_001', message, 500);
}

// =============================================================================
// OAuth 2.0 Response Builders (RFC 6749 / RFC 8628)
// =============================================================================

/**
 * Create an OAuth 2.0 error response
 * @param {string} error - OAuth error code (e.g., 'invalid_request')
 * @param {string} description - Human-readable error description
 * @param {number} status - HTTP status code (default: 400)
 * @returns {Response}
 */
export function oauthErrorResponse(error, description, status = 400) {
  return new Response(
    JSON.stringify({
      error,
      error_description: description,
    }),
    {
      status,
      headers: OAUTH_HEADERS,
    }
  );
}

/**
 * Create an OAuth 2.0 success response
 * @param {Object} data - Response data
 * @param {number} status - HTTP status code (default: 200)
 * @returns {Response}
 */
export function oauthSuccessResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: OAUTH_HEADERS,
  });
}

/**
 * Pre-built OAuth error responses for common error cases
 */
export const oauthErrors = {
  /** Invalid request - missing or invalid parameters */
  invalidRequest: (description = 'Invalid request') =>
    oauthErrorResponse('invalid_request', description, 400),

  /** Invalid client credentials */
  invalidClient: (description = 'Invalid client credentials') =>
    oauthErrorResponse('invalid_client', description, 401),

  /** Invalid grant - bad auth code, refresh token, or device code */
  invalidGrant: (description = 'Invalid grant') =>
    oauthErrorResponse('invalid_grant', description, 400),

  /** Client not authorized for this grant type */
  unauthorizedClient: (description = 'Client is not authorized to use this grant type') =>
    oauthErrorResponse('unauthorized_client', description, 400),

  /** Unsupported grant type */
  unsupportedGrantType: () =>
    oauthErrorResponse('unsupported_grant_type', 'Grant type not supported', 400),

  /** Invalid or unauthorized scope */
  invalidScope: (scopes) =>
    oauthErrorResponse('invalid_scope', `Invalid scope(s): ${scopes}`, 400),

  /** Server error */
  serverError: (description = 'Internal server error') =>
    oauthErrorResponse('server_error', description, 500),

  /** User denied authorization */
  accessDenied: (description = 'User denied authorization') =>
    oauthErrorResponse('access_denied', description, 400),

  // Device Flow specific errors (RFC 8628)

  /** Device code authorization pending */
  authorizationPending: () =>
    oauthErrorResponse(
      'authorization_pending',
      'User has not yet authorized the device',
      400
    ),

  /** Polling too frequently */
  slowDown: () =>
    oauthErrorResponse(
      'slow_down',
      'Polling too frequently. Please wait longer.',
      400
    ),

  /** Device code has expired */
  expiredToken: () =>
    oauthErrorResponse('expired_token', 'Device code has expired', 400),
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Format a date to ISO date string (YYYY-MM-DD) or null
 * @param {Date|string|null} date - Date to format
 * @returns {string|null}
 */
export function formatDateString(date) {
  if (!date) return null;
  return new Date(date).toISOString().split('T')[0];
}

/**
 * Format a date to ISO datetime string or null
 * @param {Date|string|null} date - Date to format
 * @returns {string|null}
 */
export function formatDateTime(date) {
  if (!date) return null;
  return new Date(date).toISOString();
}
