import {
  describe,
  it,
  expect,
  beforeEach,
  afterEach,
  beforeAll,
  afterAll,
  vi,
} from 'vitest';
import { Auth } from '../../src/lib/auth.js';
import * as TodoDB from '../../src/lib/db.js';

// Mock the TodoDB module
vi.mock('../../src/lib/db.js', () => ({
  TodoDB: {
    getUserByUsername: vi.fn(),
    getUserByEmail: vi.fn(),
    createUser: vi.fn(),
    createSession: vi.fn(),
    getSession: vi.fn(),
    deleteSession: vi.fn(),
    cleanupExpiredSessions: vi.fn(),
  },
}));

describe('Auth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Password handling', () => {
    it('should hash password', async () => {
      const password = 'testpassword123';
      const hash = await Auth.hashPassword(password);

      expect(hash).toBeDefined();
      expect(hash).not.toBe(password);
      expect(hash.length).toBeGreaterThan(50);
    });

    it('should verify correct password', async () => {
      const password = 'testpassword123';
      const hash = await Auth.hashPassword(password);

      const isValid = await Auth.verifyPassword(password, hash);
      expect(isValid).toBe(true);
    });

    it('should reject incorrect password', async () => {
      const password = 'testpassword123';
      const wrongPassword = 'wrongpassword';
      const hash = await Auth.hashPassword(password);

      const isValid = await Auth.verifyPassword(wrongPassword, hash);
      expect(isValid).toBe(false);
    });
  });

  describe('User creation', () => {
    it('should create new user successfully', async () => {
      TodoDB.TodoDB.getUserByUsername.mockResolvedValue(undefined);
      TodoDB.TodoDB.getUserByEmail.mockResolvedValue(undefined);
      TodoDB.TodoDB.createUser.mockResolvedValue({ id: 1 });

      const result = await Auth.createUser(
        'testuser',
        'test@example.com',
        'password123'
      );

      expect(result).toBeDefined();
      expect(TodoDB.TodoDB.getUserByUsername).toHaveBeenCalledWith('testuser');
      expect(TodoDB.TodoDB.getUserByEmail).toHaveBeenCalledWith(
        'test@example.com'
      );
      expect(TodoDB.TodoDB.createUser).toHaveBeenCalledWith(
        'testuser',
        'test@example.com',
        expect.any(String)
      );
    });

    it('should throw error if username already exists', async () => {
      TodoDB.TodoDB.getUserByUsername.mockResolvedValue({
        id: 1,
        username: 'existinguser',
      });
      TodoDB.TodoDB.getUserByEmail.mockResolvedValue(undefined);

      await expect(
        Auth.createUser('existinguser', 'test@example.com', 'password123')
      ).rejects.toThrow('User already exists');
    });

    it('should throw error if email already exists', async () => {
      TodoDB.TodoDB.getUserByUsername.mockResolvedValue(undefined);
      TodoDB.TodoDB.getUserByEmail.mockResolvedValue({
        id: 1,
        email: 'existing@example.com',
      });

      await expect(
        Auth.createUser('testuser', 'existing@example.com', 'password123')
      ).rejects.toThrow('User already exists');
    });
  });

  describe('User authentication', () => {
    it('should authenticate user with correct credentials', async () => {
      const password = 'testpassword123';
      const hash = await Auth.hashPassword(password);
      const mockUser = {
        id: 1,
        username: 'testuser',
        password_hash: hash,
      };

      TodoDB.TodoDB.getUserByUsername.mockResolvedValue(mockUser);

      const result = await Auth.authenticateUser('testuser', password);

      expect(result).toEqual(mockUser);
      expect(TodoDB.TodoDB.getUserByUsername).toHaveBeenCalledWith('testuser');
    });

    it('should throw error for non-existent user', async () => {
      TodoDB.TodoDB.getUserByUsername.mockResolvedValue(undefined);

      await expect(
        Auth.authenticateUser('nonexistent', 'password123')
      ).rejects.toThrow('Invalid credentials');
    });

    it('should throw error for incorrect password', async () => {
      const correctPassword = 'correctpassword';
      const wrongPassword = 'wrongpassword';
      const hash = await Auth.hashPassword(correctPassword);
      const mockUser = {
        id: 1,
        username: 'testuser',
        password_hash: hash,
      };

      TodoDB.TodoDB.getUserByUsername.mockResolvedValue(mockUser);

      await expect(
        Auth.authenticateUser('testuser', wrongPassword)
      ).rejects.toThrow('Invalid credentials');
    });
  });

  describe('Session management', () => {
    it('should create session', async () => {
      const mockSession = {
        id: 'session-uuid',
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
      };

      TodoDB.TodoDB.createSession.mockResolvedValue(mockSession);

      const result = await Auth.createSession(1);

      expect(result).toBeDefined();
      expect(result.sessionId).toBe(mockSession.id);
      expect(result.expiresAt).toBe(mockSession.expires_at);
      expect(TodoDB.TodoDB.createSession).toHaveBeenCalledWith(
        expect.any(String),
        1
      );
    });

    it('should get session user', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
      };

      TodoDB.TodoDB.getSession.mockResolvedValue(mockUser);
      TodoDB.TodoDB.cleanupExpiredSessions.mockResolvedValue();

      const result = await Auth.getSessionUser('session-id');

      expect(result).toEqual(mockUser);
      expect(TodoDB.TodoDB.cleanupExpiredSessions).toHaveBeenCalled();
      expect(TodoDB.TodoDB.getSession).toHaveBeenCalledWith('session-id');
    });

    it('should return null for invalid session', async () => {
      const result = await Auth.getSessionUser(null);
      expect(result).toBeNull();
    });

    it('should delete session', async () => {
      TodoDB.TodoDB.deleteSession.mockResolvedValue();

      await Auth.deleteSession('session-id');

      expect(TodoDB.TodoDB.deleteSession).toHaveBeenCalledWith('session-id');
    });

    it('should handle null session in delete', async () => {
      await Auth.deleteSession(null);
      expect(TodoDB.TodoDB.deleteSession).not.toHaveBeenCalled();
    });
  });

  describe('Cookie and request handling', () => {
    it('should extract session from request cookies', () => {
      const mockRequest = {
        headers: {
          get: vi.fn().mockReturnValue('session=test-session-id; other=value'),
        },
      };

      const sessionId = Auth.getSessionFromRequest(mockRequest);

      expect(sessionId).toBe('test-session-id');
      expect(mockRequest.headers.get).toHaveBeenCalledWith('cookie');
    });

    it('should return null when no cookies present', () => {
      const mockRequest = {
        headers: {
          get: vi.fn().mockReturnValue(null),
        },
      };

      const sessionId = Auth.getSessionFromRequest(mockRequest);

      expect(sessionId).toBeNull();
    });

    it('should return null when no session cookie present', () => {
      const mockRequest = {
        headers: {
          get: vi.fn().mockReturnValue('other=value; another=test'),
        },
      };

      const sessionId = Auth.getSessionFromRequest(mockRequest);

      expect(sessionId).toBeNull();
    });

    it('should create session cookie', () => {
      const sessionId = 'test-session-id';
      const expiresAt = new Date('2025-12-31T23:59:59Z');

      const cookie = Auth.createSessionCookie(sessionId, expiresAt);

      expect(cookie).toContain(`session=${sessionId}`);
      expect(cookie).toContain('HttpOnly');
      expect(cookie).toContain('Secure');
      // expect(cookie).toContain('SameSite=Strict');
      expect(cookie).toContain('Path=/');
      expect(cookie).toContain('Expires=Wed, 31 Dec 2025 23:59:59 GMT');
    });

    it('should create clear session cookie', () => {
      const cookie = Auth.clearSessionCookie();

      expect(cookie).toContain('session=');
      expect(cookie).toContain('HttpOnly');
      expect(cookie).toContain('Secure');
      // expect(cookie).toContain('SameSite=Strict');
      expect(cookie).toContain('Path=/');
      expect(cookie).toContain('Expires=Thu, 01 Jan 1970 00:00:00 GMT');
    });
  });
});
