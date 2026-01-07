/**
 * Centralized application configuration
 * All magic numbers and environment-dependent values belong here
 */

/**
 * Parse an environment variable as integer with fallback
 * @param {string} envVar - Environment variable name
 * @param {number} defaultValue - Default value if not set or invalid
 * @returns {number}
 */
function parseIntEnv(envVar, defaultValue) {
  const value = process.env[envVar];
  if (!value) return defaultValue;
  const parsed = parseInt(value, 10);
  return isNaN(parsed) ? defaultValue : parsed;
}

/**
 * Parse comma-separated environment variable as array
 * @param {string} envVar - Environment variable name
 * @param {string[]} defaultValue - Default value if not set
 * @returns {string[]}
 */
function parseArrayEnv(envVar, defaultValue) {
  const value = process.env[envVar];
  if (!value) return defaultValue;
  return value.split(',').map(s => s.trim()).filter(Boolean);
}

export const config = {
  // ==========================================================================
  // Security - Password Hashing
  // ==========================================================================
  auth: {
    /** BCrypt hashing rounds (higher = more secure but slower) */
    bcryptRounds: parseIntEnv('BCRYPT_ROUNDS', 12),

    /** Session duration in days */
    sessionDurationDays: parseIntEnv('SESSION_DURATION_DAYS', 7),

    /** Session cookie name (uses __Host- prefix in production for security) */
    sessionCookieName: process.env.NODE_ENV === 'production' ? '__Host-session' : 'session',

    /** Maximum login attempts before rate limiting */
    maxLoginAttempts: parseIntEnv('LOGIN_MAX_ATTEMPTS', 5),

    /** Rate limit window in milliseconds (default: 15 minutes) */
    rateLimitWindowMs: parseIntEnv('LOGIN_WINDOW_MS', 15 * 60 * 1000),
  },

  // ==========================================================================
  // OAuth 2.0 Configuration
  // ==========================================================================
  oauth: {
    /** Access token expiry in seconds (default: 1 hour) */
    accessTokenExpirySeconds: parseIntEnv('ACCESS_TOKEN_EXPIRY', 3600),

    /** Authorization code expiry in minutes (default: 10 minutes) */
    authorizationCodeExpiryMinutes: parseIntEnv('AUTH_CODE_EXPIRY', 10),

    /** Device code expiry in seconds (default: 30 minutes) */
    deviceCodeExpirySeconds: parseIntEnv('DEVICE_CODE_EXPIRY', 1800),

    /** Minimum device polling interval in seconds */
    devicePollIntervalSeconds: parseIntEnv('DEVICE_POLL_INTERVAL', 5),
  },

  // ==========================================================================
  // CORS Configuration
  // ==========================================================================
  cors: {
    /** Allowed origins for cross-origin requests */
    allowedOrigins: parseArrayEnv('ALLOWED_ORIGINS', [
      'https://todo.brooksmcmillin.com',
      // Development origins (only if not in production)
      ...(process.env.NODE_ENV !== 'production' ? [
        'http://localhost:4321',
        'http://localhost:3000',
        'http://127.0.0.1:4321',
        'http://127.0.0.1:3000',
      ] : []),
    ]),
  },

  // ==========================================================================
  // Rate Limiting
  // ==========================================================================
  rateLimit: {
    /** Cleanup interval for expired rate limit entries (5 minutes) */
    cleanupIntervalMs: 5 * 60 * 1000,

    /** Maximum age for rate limit entries (1 hour) */
    maxAgeMs: 60 * 60 * 1000,
  },

  // ==========================================================================
  // Database
  // ==========================================================================
  database: {
    /** Build connection string from environment variables */
    get connectionString() {
      return 'postgresql://' +
        process.env.POSTGRES_USER + ':' +
        process.env.POSTGRES_PASSWORD + '@' +
        (process.env.POSTGRES_HOST || 'localhost') + ':5432/' +
        process.env.POSTGRES_DB;
    },
  },

  // ==========================================================================
  // Validation Rules
  // ==========================================================================
  validation: {
    /** Minimum password length */
    minPasswordLength: 8,

    /** Minimum client secret length */
    minClientSecretLength: 32,

    /** Maximum field lengths */
    maxUsernameLength: 50,
    maxEmailLength: 255,
    maxProjectNameLength: 100,
    maxTodoTitleLength: 255,
  },

  // ==========================================================================
  // Environment
  // ==========================================================================
  env: {
    isProduction: process.env.NODE_ENV === 'production',
    isDevelopment: process.env.NODE_ENV !== 'production',
  },
};

// For backwards compatibility, also export CONFIG (used by recovered db.js)
export const CONFIG = {
  BCRYPT_ROUNDS: config.auth.bcryptRounds,
  SESSION_DURATION_DAYS: config.auth.sessionDurationDays,
  SESSION_COOKIE_NAME: config.auth.sessionCookieName,
  ACCESS_TOKEN_EXPIRY_SECONDS: config.oauth.accessTokenExpirySeconds,
  AUTHORIZATION_CODE_EXPIRY_MINUTES: config.oauth.authorizationCodeExpiryMinutes,
  DEVICE_CODE_EXPIRY_SECONDS: config.oauth.deviceCodeExpirySeconds,
  DEVICE_POLL_INTERVAL_SECONDS: config.oauth.devicePollIntervalSeconds,
  LOGIN_MAX_ATTEMPTS: config.auth.maxLoginAttempts,
  LOGIN_WINDOW_MS: config.auth.rateLimitWindowMs,
  RATE_LIMIT_CLEANUP_INTERVAL_MS: config.rateLimit.cleanupIntervalMs,
  RATE_LIMIT_MAX_AGE_MS: config.rateLimit.maxAgeMs,
};

export default config;
