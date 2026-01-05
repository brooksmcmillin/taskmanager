/**
 * Simple in-memory rate limiter for authentication endpoints.
 * In production, consider using Redis for distributed rate limiting.
 */

class RateLimiter {
  constructor() {
    // Map of identifier -> array of attempt timestamps
    this.attempts = new Map();
    // Clean up old entries every 5 minutes
    setInterval(() => this.cleanup(), 5 * 60 * 1000);
  }

  /**
   * Check if the identifier is rate limited
   * @param {string} identifier - IP address or username
   * @param {number} maxAttempts - Maximum attempts allowed
   * @param {number} windowMs - Time window in milliseconds
   * @returns {{ allowed: boolean, retryAfter?: number }}
   */
  check(identifier, maxAttempts = 5, windowMs = 15 * 60 * 1000) {
    const now = Date.now();
    const attempts = this.attempts.get(identifier) || [];

    // Filter to only recent attempts within the window
    const recentAttempts = attempts.filter(t => now - t < windowMs);

    if (recentAttempts.length >= maxAttempts) {
      // Calculate when the oldest attempt will expire
      const oldestAttempt = Math.min(...recentAttempts);
      const retryAfter = Math.ceil((oldestAttempt + windowMs - now) / 1000);
      return { allowed: false, retryAfter };
    }

    return { allowed: true };
  }

  /**
   * Record an attempt for the identifier
   * @param {string} identifier - IP address or username
   */
  recordAttempt(identifier) {
    const now = Date.now();
    const attempts = this.attempts.get(identifier) || [];
    attempts.push(now);
    this.attempts.set(identifier, attempts);
  }

  /**
   * Clear attempts for an identifier (e.g., after successful login)
   * @param {string} identifier - IP address or username
   */
  clearAttempts(identifier) {
    this.attempts.delete(identifier);
  }

  /**
   * Clean up expired entries
   */
  cleanup() {
    const now = Date.now();
    const maxAge = 60 * 60 * 1000; // 1 hour

    for (const [identifier, attempts] of this.attempts.entries()) {
      const recentAttempts = attempts.filter(t => now - t < maxAge);
      if (recentAttempts.length === 0) {
        this.attempts.delete(identifier);
      } else {
        this.attempts.set(identifier, recentAttempts);
      }
    }
  }
}

// Singleton instance for login rate limiting
export const loginRateLimiter = new RateLimiter();
