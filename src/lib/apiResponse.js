/**
 * API Response utilities for consistent JSON responses
 */

const JSON_HEADERS = { 'Content-Type': 'application/json' };

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
