import bcrypt from 'bcryptjs';
import { randomUUID } from 'crypto';
import { TodoDB } from './db.js';
import { config } from 'dotenv';

config();

export async function requireAuth(request) {
  // First try Bearer token authentication (for OAuth2 access tokens)
  const authHeader = request.headers.get('authorization');
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.substring(7);
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

export class Auth {
  static async hashPassword(password) {
    return await bcrypt.hash(password, 12);
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
    if (!user) {
      throw new Error('Invalid credentials');
    }

    const isValid = await this.verifyPassword(password, user.password_hash);
    if (!isValid) {
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

    const sessionCookie = cookies
      .split(';')
      .find((cookie) => cookie.trim().startsWith('session='));

    if (!sessionCookie) return null;

    return sessionCookie.split('=')[1];
  }

  static createSessionCookie(sessionId, expiresAt) {
    const expires = new Date(expiresAt).toUTCString();
    const isProduction = process.env.NODE_ENV === 'production';
    const isLocalhost =
      process.env.NODE_ENV === 'development' ||
      (typeof window !== 'undefined' &&
        window.location.hostname === 'localhost');

    let cookieString = `session=${sessionId}; HttpOnly; SameSite=Lax; Path=/; Expires=${expires}`;

    if (isProduction) {
      cookieString += '; Secure; Domain=.' + process.env.ROOT_DOMAIN;
    } else {
      // For localhost, don't set Domain and don't require Secure
      cookieString += '';
    }

    return cookieString;
  }

  static clearSessionCookie() {
    const isProduction = process.env.NODE_ENV === 'production';

    let cookieString =
      'session=; HttpOnly; SameSite=Lax; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT';

    if (isProduction) {
      cookieString += '; Secure; Domain=.' + process.env.ROOT_DOMAIN;
    }

    return cookieString;
  }
}
