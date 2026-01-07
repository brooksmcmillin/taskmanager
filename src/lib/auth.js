import bcrypt from 'bcryptjs';
import { randomUUID } from 'crypto';
import { TodoDB } from './db.js';
import { CONFIG } from './config.js';

/**
 * Authentication helper utilities
 * Consolidates common auth-related operations
 */

/**
 * Extract Bearer token from Authorization header
 * @param {Request} request - The incoming request
 * @returns {string|null} The token or null if not present/invalid
 */
export function extractBearerToken(request) {
  const authHeader =
    request.headers.get('Authorization') ||
    request.headers.get('authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return null;
  }
  return authHeader.substring(7);
}

export async function requireAuth(request) {
  // First try Bearer token authentication (for OAuth2 access tokens)
  const token = extractBearerToken(request);
  if (token) {
    const tokenData = await TodoDB.getAccessToken(token);
    if (tokenData) {
      return {
        user_id: tokenData.user_id,
        username: tokenData.username,
        // Mark as token-based auth for potential scope checking
        auth_type: 'bearer',
        scopes: JSON.parse(tokenData.scopes || '[]'),
      };
    }
  }

  // Fall back to session-based authentication
  const sessionId = await Auth.getSessionFromRequest(request);
  const session = await Auth.getSessionUser(sessionId);

  if (!session) {
    throw new Error('Authentication required');
  }

  return { ...session, auth_type: 'session' };
}

/**
 * Check authentication for Astro pages (non-throwing version)
 * Returns { user } if authenticated, or { redirect } if not
 */
export function checkAuth(request) {
  const sessionId = Auth.getSessionFromRequest(request);

  if (!sessionId) {
    return {
      redirect: new Response(null, {
        status: 302,
        headers: { Location: '/login' },
      }),
    };
  }

  // Return a promise-like structure for sync checking
  // The actual user fetch happens async, so we return a wrapper
  return {
    user: null,
    sessionId,
    async getUser() {
      const user = await Auth.getSessionUser(this.sessionId);
      if (!user) {
        return {
          redirect: new Response(null, {
            status: 302,
            headers: { Location: '/login' },
          }),
        };
      }
      return { user };
    },
  };
}

/**
 * Async version of checkAuth for Astro pages
 */
export async function checkAuthAsync(request) {
  const sessionId = Auth.getSessionFromRequest(request);

  if (!sessionId) {
    return {
      redirect: new Response(null, {
        status: 302,
        headers: { Location: '/login' },
      }),
    };
  }

  const user = await Auth.getSessionUser(sessionId);

  if (!user) {
    return {
      redirect: new Response(null, {
        status: 302,
        headers: { Location: '/login' },
      }),
    };
  }

  return { user };
}

export class Auth {
  static async hashPassword(password) {
    return await bcrypt.hash(password, CONFIG.BCRYPT_ROUNDS);
  }

  static async verifyPassword(password, hash) {
    return await bcrypt.compare(password, hash);
  }

  static async createUser(username, email, password) {
    const existingUser =
      (await TodoDB.getUserByUsername(username)) ||
      (await TodoDB.getUserByEmail(email));
    if (existingUser && existingUser != '') {
      throw new Error('User already exists');
    }

    const passwordHash = await this.hashPassword(password);
    return await TodoDB.createUser(username, email, passwordHash);
  }

  static async authenticateUser(username, password) {
    const user = await TodoDB.getUserByUsername(username);

    // Use constant-time comparison to prevent timing attacks
    // Always perform password verification even if user doesn't exist
    const dummyHash = '$2a$12$dummy.hash.to.prevent.timing.attacks.placeholder';
    const passwordHash = user ? user.password_hash : dummyHash;
    const isValid = await this.verifyPassword(password, passwordHash);

    if (!user || !isValid) {
      throw new Error('Invalid credentials');
    }

    return user;
  }

  static async createSession(userId) {
    const sessionId = randomUUID();

    const session = await TodoDB.createSession(sessionId, userId);
    return {
      sessionId: session.id,
      expiresAt: session.expires_at,
    };
  }

  static async getSessionUser(sessionId) {
    if (!sessionId) {
      return null;
    }

    // Clean up expired sessions periodically
    await TodoDB.cleanupExpiredSessions();

    const user = await TodoDB.getSession(sessionId);

    return user;
  }

  static async deleteSession(sessionId) {
    if (sessionId) {
      await TodoDB.deleteSession(sessionId);
    }
  }

  static getSessionFromRequest(request) {
    const cookies = request.headers.get('cookie');

    if (!cookies) return null;

    // Check for __Host-session first (production), then fall back to session (development)
    const sessionCookie = cookies
      .split(';')
      .find(
        (cookie) =>
          cookie.trim().startsWith('__Host-session=') ||
          cookie.trim().startsWith('session=')
      );

    if (!sessionCookie) return null;

    // Handle both cookie names
    const trimmed = sessionCookie.trim();
    if (trimmed.startsWith('__Host-session=')) {
      return trimmed.substring('__Host-session='.length);
    }
    return trimmed.split('=')[1];
  }

  static createSessionCookie(sessionId, expiresAt) {
    const expires = new Date(expiresAt).toUTCString();
    const isProduction = process.env.NODE_ENV === 'production';

    // In production, use __Host- prefix for maximum security
    // __Host- requires: Secure, Path=/, and NO Domain attribute
    // SameSite=Lax allows cookies on top-level navigations (form submissions, links)
    // while protecting against CSRF from embedded content. Using Lax instead of Strict
    // to support OAuth flows where users are redirected from external auth servers.
    if (isProduction) {
      return `__Host-session=${sessionId}; HttpOnly; SameSite=Lax; Path=/; Expires=${expires}; Secure`;
    }

    // For development, use regular cookie without __Host- prefix (requires Secure)
    return `session=${sessionId}; HttpOnly; SameSite=Lax; Path=/; Expires=${expires}`;
  }

  static clearSessionCookie() {
    const isProduction = process.env.NODE_ENV === 'production';

    // Match the cookie name used in createSessionCookie
    if (isProduction) {
      return '__Host-session=; HttpOnly; SameSite=Lax; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure';
    }

    return 'session=; HttpOnly; SameSite=Lax; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT';
  }
}
