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
import { POST as loginPost } from '../../src/pages/api/auth/login.js';
import { POST as registerPost } from '../../src/pages/api/auth/register.js';
import { POST as logoutPost } from '../../src/pages/api/auth/logout.js';
import { Auth } from '../../src/lib/auth.js';

// Mock the Auth module
vi.mock('../../src/lib/auth.js', () => ({
  Auth: {
    getSessionFromRequest: vi.fn(),
    getSessionUser: vi.fn(),
    authenticateUser: vi.fn(),
    createSession: vi.fn(),
    createSessionCookie: vi.fn(),
    deleteSession: vi.fn(),
    clearSessionCookie: vi.fn(),
    createUser: vi.fn(),
  },
}));

describe('Auth API Endpoints', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('POST /api/auth/login', () => {
    it('should login user with valid credentials', async () => {
      const mockUser = {
        id: 1,
        username: 'testuser',
        email: 'test@example.com',
      };
      const mockSession = { sessionId: 'session-123', expiresAt: new Date() };

      Auth.authenticateUser.mockResolvedValue(mockUser);
      Auth.createSession.mockResolvedValue(mockSession);
      Auth.createSessionCookie.mockReturnValue('session=session-123; HttpOnly');

      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'testuser',
          password: 'password123',
        }),
      };

      const response = await loginPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData.success).toBe(true);
      expect(responseData.user).toEqual(mockUser);
      expect(response.headers.get('Set-Cookie')).toBe(
        'session=session-123; HttpOnly'
      );
    });

    it('should return 400 for missing username', async () => {
      const request = {
        json: vi.fn().mockResolvedValue({
          password: 'password123',
        }),
      };

      const response = await loginPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
      expect(responseData.error).toBe('Username and password required');
    });

    it('should return 400 for missing password', async () => {
      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'testuser',
        }),
      };

      const response = await loginPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
      expect(responseData.error).toBe('Username and password required');
    });

    it('should return 401 for invalid credentials', async () => {
      Auth.authenticateUser.mockRejectedValue(new Error('Invalid credentials'));

      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'testuser',
          password: 'wrongpassword',
        }),
      };

      const response = await loginPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Invalid credentials');
    });
  });

  describe('POST /api/auth/register', () => {
    it('should register new user successfully', async () => {
      const mockUser = { id: 1 };
      Auth.createUser.mockResolvedValue(mockUser);

      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'newuser',
          email: 'new@example.com',
          password: 'password123',
        }),
      };

      const response = await registerPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(201);
      expect(responseData.success).toBe(true);
      expect(responseData.message).toBe('User created successfully');
      expect(responseData.userId).toBe(1);
    });

    it('should return 400 for missing fields', async () => {
      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'newuser',
          password: 'password123',
          // missing email
        }),
      };

      const response = await registerPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
      expect(responseData.error).toBe('Missing required fields');
    });

    it('should return 400 for short password', async () => {
      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'newuser',
          email: 'new@example.com',
          password: '123',
        }),
      };

      const response = await registerPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
      expect(responseData.error).toBe('Password must be at least 6 characters');
    });

    it('should return 400 for duplicate user', async () => {
      Auth.createUser.mockRejectedValue(new Error('User already exists'));

      const request = {
        json: vi.fn().mockResolvedValue({
          username: 'existinguser',
          email: 'existing@example.com',
          password: 'password123',
        }),
      };

      const response = await registerPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
      expect(responseData.error).toBe('User already exists');
    });
  });

  describe('POST /api/auth/logout', () => {
    it('should logout successfully with valid session', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.deleteSession.mockResolvedValue();
      Auth.clearSessionCookie.mockReturnValue(
        'session=; HttpOnly; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
      );

      const request = {
        headers: {
          get: vi.fn().mockReturnValue('session=session-123'),
        },
      };

      const response = await logoutPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData.success).toBe(true);
      expect(Auth.deleteSession).toHaveBeenCalledWith('session-123');
      expect(response.headers.get('Set-Cookie')).toContain('session=');
    });

    it('should logout successfully even without session', async () => {
      Auth.getSessionFromRequest.mockReturnValue(null);
      Auth.clearSessionCookie.mockReturnValue(
        'session=; HttpOnly; Expires=Thu, 01 Jan 1970 00:00:00 GMT'
      );

      const request = {
        headers: {
          get: vi.fn().mockReturnValue(null),
        },
      };

      const response = await logoutPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData.success).toBe(true);
      expect(Auth.deleteSession).not.toHaveBeenCalled();
    });
  });
});
