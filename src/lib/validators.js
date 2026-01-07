/**
 * Input validation utilities
 * Consolidates validation logic used across API endpoints
 */

import { config } from './config.js';
import { errors } from './errors.js';

// =============================================================================
// Validation Result Type
// =============================================================================

/**
 * @typedef {Object} ValidationResult
 * @property {boolean} valid - Whether validation passed
 * @property {ApiError|null} error - Error if validation failed
 * @property {*} [value] - Sanitized/transformed value if applicable
 */

// =============================================================================
// String Validators
// =============================================================================

/**
 * Validate that a value is a non-empty string
 * @param {*} value - Value to validate
 * @param {string} fieldName - Field name for error messages
 * @returns {ValidationResult}
 */
export function validateRequired(value, fieldName) {
  if (value === undefined || value === null || value === '') {
    return { valid: false, error: errors.required(fieldName) };
  }
  if (typeof value !== 'string') {
    return {
      valid: false,
      error: errors.invalid(fieldName, 'must be a string'),
    };
  }
  return { valid: true, error: null, value: value.trim() };
}

/**
 * Validate string length
 * @param {string} value - String to validate
 * @param {string} fieldName - Field name for error messages
 * @param {number} [min] - Minimum length
 * @param {number} [max] - Maximum length
 * @returns {ValidationResult}
 */
export function validateLength(value, fieldName, min = null, max = null) {
  if (min !== null && value.length < min) {
    return { valid: false, error: errors.tooShort(fieldName, min) };
  }
  if (max !== null && value.length > max) {
    return { valid: false, error: errors.tooLong(fieldName, max) };
  }
  return { valid: true, error: null, value };
}

// =============================================================================
// Email Validation
// =============================================================================

/** Email regex pattern */
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {ValidationResult}
 */
export function validateEmail(email) {
  const required = validateRequired(email, 'Email');
  if (!required.valid) return required;

  const normalized = required.value.toLowerCase();

  if (!EMAIL_REGEX.test(normalized)) {
    return { valid: false, error: errors.invalidEmail() };
  }

  if (normalized.length > config.validation.maxEmailLength) {
    return {
      valid: false,
      error: errors.tooLong('Email', config.validation.maxEmailLength),
    };
  }

  return { valid: true, error: null, value: normalized };
}

// =============================================================================
// Password Validation
// =============================================================================

/**
 * Validate password meets security requirements
 * @param {string} password - Password to validate
 * @returns {ValidationResult}
 */
export function validatePassword(password) {
  const required = validateRequired(password, 'Password');
  if (!required.valid) return required;

  const pwd = required.value;
  const minLength = config.validation.minPasswordLength;

  // Check minimum length
  if (pwd.length < minLength) {
    return {
      valid: false,
      error: errors.weakPassword(`must be at least ${minLength} characters`),
    };
  }

  // Check for character diversity
  const hasLower = /[a-z]/.test(pwd);
  const hasUpper = /[A-Z]/.test(pwd);
  const hasNumber = /[0-9]/.test(pwd);
  const hasSpecial = /[^a-zA-Z0-9]/.test(pwd);

  const diversityCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(
    Boolean
  ).length;

  if (diversityCount < 2) {
    return {
      valid: false,
      error: errors.weakPassword(
        'must contain at least 2 of: lowercase, uppercase, numbers, special characters'
      ),
    };
  }

  return { valid: true, error: null, value: pwd };
}

// =============================================================================
// Username Validation
// =============================================================================

/** Username allowed characters regex */
const USERNAME_REGEX = /^[a-zA-Z][a-zA-Z0-9_-]*$/;

/**
 * Validate username format
 * @param {string} username - Username to validate
 * @returns {ValidationResult}
 */
export function validateUsername(username) {
  const required = validateRequired(username, 'Username');
  if (!required.valid) return required;

  const name = required.value;

  if (name.length < 3) {
    return { valid: false, error: errors.tooShort('Username', 3) };
  }

  if (name.length > config.validation.maxUsernameLength) {
    return {
      valid: false,
      error: errors.tooLong('Username', config.validation.maxUsernameLength),
    };
  }

  if (!USERNAME_REGEX.test(name)) {
    return {
      valid: false,
      error: errors.invalid(
        'Username',
        'must start with a letter and contain only letters, numbers, underscores, and hyphens'
      ),
    };
  }

  return { valid: true, error: null, value: name };
}

// =============================================================================
// OAuth Client Secret Validation
// =============================================================================

/**
 * Validate OAuth client secret meets security requirements
 * @param {string} secret - Client secret to validate
 * @returns {ValidationResult}
 */
export function validateClientSecret(secret) {
  const required = validateRequired(secret, 'Client secret');
  if (!required.valid) return required;

  const minLength = config.validation.minClientSecretLength;

  if (secret.length < minLength) {
    return {
      valid: false,
      error: errors.validation(
        `Client secret must be at least ${minLength} characters`,
        'clientSecret'
      ),
    };
  }

  // Check for character diversity
  const hasLower = /[a-z]/.test(secret);
  const hasUpper = /[A-Z]/.test(secret);
  const hasNumber = /[0-9]/.test(secret);
  const hasSpecial = /[^a-zA-Z0-9]/.test(secret);

  const diversityCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(
    Boolean
  ).length;

  if (diversityCount < 2) {
    return {
      valid: false,
      error: errors.validation(
        'Client secret must contain at least 2 of: lowercase, uppercase, numbers, special characters',
        'clientSecret'
      ),
    };
  }

  return { valid: true, error: null, value: secret };
}

// =============================================================================
// URL Validation
// =============================================================================

/**
 * Validate URL format (for redirect URIs, etc.)
 * @param {string} url - URL to validate
 * @param {Object} [options] - Validation options
 * @param {boolean} [options.requireHttps] - Require HTTPS (default: false in dev, true in prod)
 * @param {boolean} [options.allowLocalhost] - Allow localhost URLs (default: true in dev)
 * @returns {ValidationResult}
 */
export function validateUrl(url, options = {}) {
  const required = validateRequired(url, 'URL');
  if (!required.valid) return required;

  const {
    requireHttps = config.env.isProduction,
    allowLocalhost = config.env.isDevelopment,
  } = options;

  try {
    const parsed = new URL(required.value);

    // Check protocol
    if (requireHttps && parsed.protocol !== 'https:') {
      // Allow localhost exception if enabled
      const isLocalhost =
        parsed.hostname === 'localhost' || parsed.hostname === '127.0.0.1';
      if (!allowLocalhost || !isLocalhost) {
        return {
          valid: false,
          error: errors.invalidUrl('URL must use HTTPS'),
        };
      }
    }

    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return {
        valid: false,
        error: errors.invalidUrl('URL must use HTTP or HTTPS'),
      };
    }

    return { valid: true, error: null, value: required.value };
  } catch {
    return { valid: false, error: errors.invalidUrl() };
  }
}

/**
 * Validate array of redirect URIs
 * @param {string[]} uris - Array of URIs to validate
 * @returns {ValidationResult}
 */
export function validateRedirectUris(uris) {
  if (!Array.isArray(uris) || uris.length === 0) {
    return {
      valid: false,
      error: errors.validation(
        'At least one redirect URI is required',
        'redirectUris'
      ),
    };
  }

  for (const uri of uris) {
    const result = validateUrl(uri);
    if (!result.valid) {
      return {
        valid: false,
        error: errors.validation(
          `Invalid redirect URI: ${uri}`,
          'redirectUris'
        ),
      };
    }
  }

  return { valid: true, error: null, value: uris };
}

// =============================================================================
// Numeric Validation
// =============================================================================

/**
 * Parse and validate integer parameter
 * @param {string|number} value - Value to parse
 * @param {string} fieldName - Field name for error messages
 * @param {Object} [options] - Validation options
 * @param {number} [options.min] - Minimum value
 * @param {number} [options.max] - Maximum value
 * @returns {ValidationResult}
 */
export function validateInteger(value, fieldName, options = {}) {
  const { min = null, max = null } = options;

  const parsed = parseInt(value, 10);

  if (isNaN(parsed)) {
    return {
      valid: false,
      error: errors.invalid(fieldName, 'must be a valid integer'),
    };
  }

  if (min !== null && parsed < min) {
    return {
      valid: false,
      error: errors.invalid(fieldName, `must be at least ${min}`),
    };
  }

  if (max !== null && parsed > max) {
    return {
      valid: false,
      error: errors.invalid(fieldName, `must be at most ${max}`),
    };
  }

  return { valid: true, error: null, value: parsed };
}

/**
 * Validate positive integer (for IDs, etc.)
 * @param {string|number} value - Value to validate
 * @param {string} fieldName - Field name for error messages
 * @returns {ValidationResult}
 */
export function validateId(value, fieldName = 'ID') {
  return validateInteger(value, fieldName, { min: 1 });
}

// =============================================================================
// OAuth Scope Validation
// =============================================================================

/** Valid OAuth scopes */
const VALID_SCOPES = ['read', 'write', 'admin'];

/**
 * Validate OAuth scopes
 * @param {string|string[]} scopes - Scopes to validate (string or array)
 * @param {string[]} [allowedScopes] - Allowed scopes for this client
 * @returns {ValidationResult}
 */
export function validateScopes(scopes, allowedScopes = VALID_SCOPES) {
  // Parse scopes if string
  const scopeArray =
    typeof scopes === 'string'
      ? scopes.split(/[\s,]+/).filter(Boolean)
      : scopes;

  if (!Array.isArray(scopeArray) || scopeArray.length === 0) {
    return { valid: true, error: null, value: ['read'] }; // Default scope
  }

  const invalidScopes = scopeArray.filter((s) => !allowedScopes.includes(s));

  if (invalidScopes.length > 0) {
    return {
      valid: false,
      error: errors.oauthInvalidScope(invalidScopes.join(', ')),
    };
  }

  return { valid: true, error: null, value: scopeArray };
}

// =============================================================================
// Grant Type Validation
// =============================================================================

/** Valid OAuth grant types */
const VALID_GRANT_TYPES = [
  'authorization_code',
  'refresh_token',
  'client_credentials',
  'device_code',
];

/**
 * Validate OAuth grant types
 * @param {string|string[]} grantTypes - Grant types to validate
 * @returns {ValidationResult}
 */
export function validateGrantTypes(grantTypes) {
  const typesArray =
    typeof grantTypes === 'string'
      ? grantTypes.split(/[\s,]+/).filter(Boolean)
      : grantTypes;

  if (!Array.isArray(typesArray) || typesArray.length === 0) {
    return { valid: true, error: null, value: ['authorization_code'] }; // Default
  }

  const invalidTypes = typesArray.filter((t) => !VALID_GRANT_TYPES.includes(t));

  if (invalidTypes.length > 0) {
    return {
      valid: false,
      error: errors.validation(
        `Invalid grant type(s): ${invalidTypes.join(', ')}`,
        'grantTypes'
      ),
    };
  }

  return { valid: true, error: null, value: typesArray };
}

// =============================================================================
// Composite Validators
// =============================================================================

/**
 * Validate all fields and return first error or all validated values
 * @param {Object.<string, ValidationResult>} validations - Object of field -> validation result
 * @returns {{ valid: boolean, error: ApiError|null, values: Object }}
 */
export function validateAll(validations) {
  const values = {};

  for (const [field, result] of Object.entries(validations)) {
    if (!result.valid) {
      return { valid: false, error: result.error, values: null };
    }
    values[field] = result.value;
  }

  return { valid: true, error: null, values };
}

export default {
  validateRequired,
  validateLength,
  validateEmail,
  validatePassword,
  validateUsername,
  validateClientSecret,
  validateUrl,
  validateRedirectUris,
  validateInteger,
  validateId,
  validateScopes,
  validateGrantTypes,
  validateAll,
};
