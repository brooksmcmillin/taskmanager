import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';
import { TodoDB } from './db.js';

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
    const sessionId = uuidv4();

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
    return `session=${sessionId}; HttpOnly; Secure; SameSite=Lax; Path=/; Domain=.brooksmcmillin.com; Expires=${expires}`;
  }

  static clearSessionCookie() {
    return 'session=; HttpOnly; Secure; SameSite=Lax; Path=/; Domain=.brooksmcmillin.com; Expires=Thu, 01 Jan 1970 00:00:00 GMT';
  }
}
