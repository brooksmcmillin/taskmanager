import bcrypt from 'bcryptjs';
import { v4 as uuidv4 } from 'uuid';
import { TodoDB } from './db.js';

const SESSION_DURATION = 7 * 24 * 60 * 60 * 1000; // 7 days in milliseconds

export class Auth {
  static async hashPassword(password) {
    return await bcrypt.hash(password, 12);
  }

  static async verifyPassword(password, hash) {
    return await bcrypt.compare(password, hash);
  }

  static async createUser(username, email, password) {
    const existingUser = TodoDB.getUserByUsername(username) || TodoDB.getUserByEmail(email);
    if (existingUser) {
      throw new Error('User already exists');
    }

    const passwordHash = await this.hashPassword(password);
    return TodoDB.createUser(username, email, passwordHash);
  }

  static async authenticateUser(username, password) {
    const user = TodoDB.getUserByUsername(username);
    if (!user) {
      throw new Error('Invalid credentials');
    }

    const isValid = await this.verifyPassword(password, user.password_hash);
    if (!isValid) {
      throw new Error('Invalid credentials');
    }

    return user;
  }

  static createSession(userId) {
    const sessionId = uuidv4();
    const expiresAt = Date.now() + SESSION_DURATION;
    
    TodoDB.createSession(sessionId, userId, expiresAt);
    return { sessionId, expiresAt };
  }

  static getSessionUser(sessionId) {
    if (!sessionId) return null;
    
    // Clean up expired sessions periodically
    TodoDB.cleanupExpiredSessions();
    
    return TodoDB.getSession(sessionId);
  }

  static deleteSession(sessionId) {
    if (sessionId) {
      TodoDB.deleteSession(sessionId);
    }
  }

  static getSessionFromRequest(request) {
    const cookies = request.headers.get('cookie');
    if (!cookies) return null;

    const sessionCookie = cookies
      .split(';')
      .find(cookie => cookie.trim().startsWith('session='));
    
    if (!sessionCookie) return null;

    return sessionCookie.split('=')[1];
  }

  static createSessionCookie(sessionId, expiresAt) {
    const expires = new Date(expiresAt).toUTCString();
    return `session=${sessionId}; HttpOnly; Secure; SameSite=Strict; Path=/; Expires=${expires}`;
  }

  static clearSessionCookie() {
    return 'session=; HttpOnly; Secure; SameSite=Strict; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT';
  }
}