/**
 * API Response utilities for consistent JSON responses
 */

const JSON_HEADERS = { 'Content-Type': 'application/json' };

/**
 * Allowed CORS origins for OAuth endpoints.
 * In production, this should be configured via environment variables.
 * Note: OAuth clients making requests must be from allowed origins.
 */
const ALLOWED_ORIGINS = [
  'https://todo.brooksmcmillin.com',
  // Add localhost for development
  ...(process.env.NODE_ENV !== 'production'
    ? [
        'http://localhost:4321',
        'http://localhost:3000',
        'http://127.0.0.1:4321',
        'http://127.0.0.1:3000',
      ]
    : []),
];

/**
 * Get CORS headers for a request, validating the origin.
 * Returns headers with the specific origin if allowed, or null if not allowed.
 * @param {Request} request - The incoming request
 * @returns {Object} CORS headers object
 */
export function getCorsHeaders(request) {
  const origin = request.headers.get('origin');

  // If no origin (same-origin request or non-browser client), allow
  if (!origin) {
    return {
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };
  }

  // Check if origin is in allowed list
  if (ALLOWED_ORIGINS.includes(origin)) {
    return {
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      Vary: 'Origin',
    };
  }

  // Origin not allowed - return empty CORS headers (browser will block)
  return {
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };
}

/**
 * Create a CORS preflight response (for OPTIONS requests)
 * @param {Request} request - The incoming request
 * @returns {Response}
 */
export function corsPreflightResponse(request) {
  return new Response(null, {
    status: 200,
    headers: getCorsHeaders(request),
  });
}

/**
 * Create a successful JSON response
 * @param {any} data - Response data
 * @param {number} status - HTTP status code (default: 200)
 * @returns {Response}
 */
export function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: JSON_HEADERS,
  });
}

/**
 * Create a success response with data
 * @param {any} data - Response data
 * @returns {Response}
 */
export function successResponse(data) {
  return jsonResponse(data, 200);
}

/**
 * Create a created response (201)
 * @param {any} data - Response data
 * @returns {Response}
 */
export function createdResponse(data) {
  return jsonResponse(data, 201);
}

/**
 * Create an error response
 * @param {string} message - Error message
 * @param {number} status - HTTP status code (default: 400)
 * @returns {Response}
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
  return errorResponse(message, 401);
}

/**
 * Create a 403 forbidden response
 * @param {string} message - Error message (default: 'Access denied')
 * @returns {Response}
 */
export function forbiddenResponse(message = 'Access denied') {
  return errorResponse(message, 403);
}

/**
 * Create a 404 not found response
 * @param {string} message - Error message (default: 'Not found')
 * @returns {Response}
 */
export function notFoundResponse(message = 'Not found') {
  return errorResponse(message, 404);
}

/**
 * Format a date to ISO date string (YYYY-MM-DD) or null
 * @param {Date|string|null} date - Date to format
 * @returns {string|null}
 */
export function formatDateString(date) {
  if (!date) return null;
  return new Date(date).toISOString().split('T')[0];
}
