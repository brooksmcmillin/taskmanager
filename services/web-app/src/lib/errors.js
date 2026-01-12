/**
 * Centralized error handling with standardized error codes
 *
 * Error Code Format: CATEGORY_NNN
 * - AUTH_*: Authentication errors (401)
 * - AUTHZ_*: Authorization errors (403)
 * - VALIDATION_*: Input validation errors (400)
 * - NOT_FOUND_*: Resource not found errors (404)
 * - OAUTH_*: OAuth-specific errors (400/401)
 * - SERVER_*: Internal server errors (500)
 */

/**
 * @typedef {Object} ApiErrorDetails
 * @property {string} code - Error code (e.g., 'AUTH_001')
 * @property {number} status - HTTP status code
 * @property {string} message - Human-readable error message
 * @property {Object} [details] - Additional error details
 */

/**
 * API Error class for consistent error handling
 */
export class ApiError extends Error {
  /**
   * @param {string} code - Error code
   * @param {number} status - HTTP status code
   * @param {string} message - Error message
   * @param {Object} [details] - Additional details
   */
  constructor(code, status, message, details = null) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.details = details;
  }

  /**
   * Convert to JSON response body
   * @returns {Object}
   */
  toJSON() {
    const response = {
      error: {
        code: this.code,
        message: this.message,
      },
    };
    if (this.details) {
      response.error.details = this.details;
    }
    return response;
  }

  /**
   * Convert to HTTP Response
   * @returns {Response}
   */
  toResponse() {
    return new Response(JSON.stringify(this.toJSON()), {
      status: this.status,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// =============================================================================
// Error Definitions
// =============================================================================

export const errors = {
  // ===========================================================================
  // Authentication Errors (401)
  // ===========================================================================

  /** Invalid username or password */
  invalidCredentials: () =>
    new ApiError('AUTH_001', 401, 'Invalid username or password'),

  /** Authentication required but not provided */
  authRequired: () => new ApiError('AUTH_002', 401, 'Authentication required'),

  /** Session has expired */
  sessionExpired: () => new ApiError('AUTH_003', 401, 'Session has expired'),

  /** Invalid or expired token */
  invalidToken: () => new ApiError('AUTH_004', 401, 'Invalid or expired token'),

  // ===========================================================================
  // Authorization Errors (403)
  // ===========================================================================

  /** User lacks permission for this action */
  forbidden: (action = 'perform this action') =>
    new ApiError('AUTHZ_001', 403, `You do not have permission to ${action}`),

  /** Resource belongs to another user */
  notOwner: (resource = 'resource') =>
    new ApiError('AUTHZ_002', 403, `You do not own this ${resource}`),

  /** Insufficient OAuth scopes */
  insufficientScope: (required) =>
    new ApiError('AUTHZ_003', 403, `Insufficient scope. Required: ${required}`),

  // ===========================================================================
  // Validation Errors (400)
  // ===========================================================================

  /** Generic validation error */
  validation: (message, field = null) =>
    new ApiError('VALIDATION_001', 400, message, field ? { field } : null),

  /** Required field is missing */
  required: (field) =>
    new ApiError('VALIDATION_002', 400, `${field} is required`, { field }),

  /** Field value is invalid */
  invalid: (field, reason = 'is invalid') =>
    new ApiError('VALIDATION_003', 400, `${field} ${reason}`, { field }),

  /** Field value too short */
  tooShort: (field, min) =>
    new ApiError(
      'VALIDATION_004',
      400,
      `${field} must be at least ${min} characters`,
      { field, min }
    ),

  /** Field value too long */
  tooLong: (field, max) =>
    new ApiError(
      'VALIDATION_005',
      400,
      `${field} must be at most ${max} characters`,
      { field, max }
    ),

  /** Invalid email format */
  invalidEmail: () =>
    new ApiError('VALIDATION_006', 400, 'Invalid email format', {
      field: 'email',
    }),

  /** Password does not meet requirements */
  weakPassword: (reason) =>
    new ApiError('VALIDATION_007', 400, `Password ${reason}`, {
      field: 'password',
    }),

  /** Invalid URL format */
  invalidUrl: (field = 'url') =>
    new ApiError('VALIDATION_008', 400, `Invalid URL format`, { field }),

  // ===========================================================================
  // Not Found Errors (404)
  // ===========================================================================

  /** Resource not found */
  notFound: (resource = 'Resource') =>
    new ApiError('NOT_FOUND_001', 404, `${resource} not found`),

  /** User not found */
  userNotFound: () => new ApiError('NOT_FOUND_002', 404, 'User not found'),

  /** Project not found */
  projectNotFound: () =>
    new ApiError('NOT_FOUND_003', 404, 'Project not found'),

  /** Task/Todo not found */
  todoNotFound: () => new ApiError('NOT_FOUND_004', 404, 'Task not found'),

  /** OAuth client not found */
  clientNotFound: () =>
    new ApiError('NOT_FOUND_005', 404, 'OAuth client not found'),

  // ===========================================================================
  // Conflict Errors (409)
  // ===========================================================================

  /** Resource already exists */
  alreadyExists: (resource = 'Resource') =>
    new ApiError('CONFLICT_001', 409, `${resource} already exists`),

  /** User already exists */
  userExists: () =>
    new ApiError(
      'CONFLICT_002',
      409,
      'User with this username or email already exists'
    ),

  // ===========================================================================
  // Rate Limiting Errors (429)
  // ===========================================================================

  /** Too many requests */
  rateLimited: (retryAfter = null) =>
    new ApiError(
      'RATE_001',
      429,
      'Too many requests. Please try again later.',
      retryAfter ? { retryAfter } : null
    ),

  // ===========================================================================
  // OAuth Errors (RFC 6749 compliant)
  // ===========================================================================

  /** Invalid OAuth request */
  oauthInvalidRequest: (description = 'Invalid request') =>
    new ApiError('OAUTH_001', 400, description),

  /** Invalid client credentials */
  oauthInvalidClient: () =>
    new ApiError('OAUTH_002', 401, 'Invalid client credentials'),

  /** Invalid grant (auth code, refresh token, etc.) */
  oauthInvalidGrant: (description = 'Invalid grant') =>
    new ApiError('OAUTH_003', 400, description),

  /** Client not authorized for grant type */
  oauthUnauthorizedClient: (grantType) =>
    new ApiError(
      'OAUTH_004',
      400,
      `Client is not authorized to use ${grantType} grant`
    ),

  /** Unsupported grant type */
  oauthUnsupportedGrant: () =>
    new ApiError('OAUTH_005', 400, 'Unsupported grant type'),

  /** Invalid scope requested */
  oauthInvalidScope: (scopes) =>
    new ApiError('OAUTH_006', 400, `Invalid scope(s): ${scopes}`),

  /** User denied authorization */
  oauthAccessDenied: () =>
    new ApiError('OAUTH_007', 400, 'User denied authorization'),

  // Device Flow specific (RFC 8628)

  /** Authorization pending */
  oauthAuthorizationPending: () =>
    new ApiError('OAUTH_008', 400, 'Authorization pending'),

  /** Polling too fast */
  oauthSlowDown: () =>
    new ApiError('OAUTH_009', 400, 'Polling too frequently. Please slow down.'),

  /** Device code expired */
  oauthExpiredToken: () =>
    new ApiError('OAUTH_010', 400, 'Device code has expired'),

  // ===========================================================================
  // Server Errors (500)
  // ===========================================================================

  /** Internal server error */
  internal: (message = 'An unexpected error occurred') =>
    new ApiError('SERVER_001', 500, message),

  /** Database error */
  database: () => new ApiError('SERVER_002', 500, 'Database error occurred'),

  /** Configuration error */
  configError: (detail = null) =>
    new ApiError(
      'SERVER_003',
      500,
      'Server configuration error',
      detail ? { detail } : null
    ),
};

/**
 * Wrap an async handler to catch errors and convert to responses
 * @param {Function} handler - Async request handler
 * @returns {Function} Wrapped handler
 */
export function withErrorHandling(handler) {
  return async (...args) => {
    try {
      return await handler(...args);
    } catch (error) {
      if (error instanceof ApiError) {
        return error.toResponse();
      }

      // Log unexpected errors
      console.error('[Error]', error);

      // Return generic error for non-ApiErrors
      return errors.internal().toResponse();
    }
  };
}

export default errors;
