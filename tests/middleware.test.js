import { describe, it, expect, beforeEach, vi } from 'vitest';
import { onRequest, getUser, getOAuthUser } from '../src/middleware.js';
import { Auth } from '../src/lib/auth.js';
import { TodoDB } from '../src/lib/db.js';
import {
  createMockContext,
  createMockNext,
  mockAuthenticatedUser,
  mockOAuthUser,
} from './setup.js';

const url_origin = 'http://localhost:3000';

describe('Middleware Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Protected Routes', () => {
    const protectedRoutes = [
      '/',
      '/projects',
      '/api/projects',
      '/api/projects/123',
      '/api/todos',
      '/api/todos/456',
      '/api/todos/456/complete',
    ];

    it.each(protectedRoutes)(
      'should redirect to /login for unauthenticated requests to %s',
      async (route) => {
        const context = createMockContext(route);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith(
          url_origin + '/login?return_to=' + encodeURIComponent(route)
        );
        expect(result).toEqual({
          type: 'redirect',
          status: 302,
          url: url_origin + '/login?return_to=' + encodeURIComponent(route),
        });
        expect(next).not.toHaveBeenCalled();
      }
    );

    it.each(protectedRoutes)(
      'should allow authenticated requests to %s',
      async (route) => {
        const context = createMockContext(route);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue('session123');
        Auth.getSessionUser.mockResolvedValue({
          user_id: 'user123',
          username: 'testuser',
          email: 'test@example.com',
        });

        const response = await onRequest(context, next);

        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toEqual({
          id: 'user123',
          username: 'testuser',
          email: 'test@example.com',
        });
        expect(response.headers.get('X-Content-Type-Options')).toBe('nosniff');
      }
    );
  });

  describe('Unprotected Routes', () => {
    const unprotectedRoutes = [
      '/login',
      '/api/auth/login',
      '/api/oauth/token',
      '/src/styles/global.css',
    ];

    it.each(unprotectedRoutes)(
      'should not redirect unauthenticated users from unprotected route %s',
      async (route) => {
        const context = createMockContext(route);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toBeUndefined();
      }
    );
  });

  /*describe('OAuth Protected Routes', () => {
    const oauthRoutes = ['/api/oauth/authorize'];

    it.each(oauthRoutes)(
      'should redirect to /login for unauthenticated OAuth requests to %s without Bearer token',
      async (route) => {
        const context = createMockContext(route);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith('/login');
        expect(result).toEqual({
          type: 'redirect',
          status: 302,
          url: '/login',
        });
      }
    );

    it.each(oauthRoutes)(
      'should allow authenticated OAuth requests with valid Bearer token to %s',
      async (route) => {
        const context = createMockContext(route, {
          Authorization: 'Bearer valid-token',
        });
        const next = createMockNext();

        TodoDB.getAccessToken.mockResolvedValue({
          user_id: 'oauth123',
          username: 'oauthuser',
          email: 'oauth@example.com',
          scopes: '["read","write"]',
          client_id: 'client123',
        });

        const response = await onRequest(context, next);

        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toEqual(mockOAuthUser);
      }
    );*/

  /*  it('should redirect to /login for invalid OAuth token', async () => {
      const path = '/api/oauth/authorize'
      const context = createMockContext(path, {
        Authorization: 'Bearer invalid-token',
      });
      const next = createMockNext();

      TodoDB.getAccessToken.mockResolvedValue(null);
      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith(url_origin + '/login?return_to=' + encodeURIComponent(path));
      expect(result).toEqual({
        type: 'redirect',
        status: 302,
        url: url_origin + '/login?return_to=' + encodeURIComponent(path),
      });
    }); */
  //});

  describe('Security Headers', () => {
    it('should set security headers on all responses', async () => {
      const context = createMockContext('/projects');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue('session123');
      Auth.getSessionUser.mockResolvedValue({
        user_id: 'user123',
        username: 'testuser',
        email: 'test@example.com',
      });

      const response = await onRequest(context, next);

      expect(response.headers.get('X-Content-Type-Options')).toBe('nosniff');
      expect(response.headers.get('X-Frame-Options')).toBe('DENY');
      expect(response.headers.get('X-XSS-Protection')).toBe('1; mode=block');
      expect(response.headers.get('Referrer-Policy')).toBe(
        'strict-origin-when-cross-origin'
      );
      expect(response.headers.get('Permissions-Policy')).toContain(
        'accelerometer=()'
      );
    });

    it('should remove X-Powered-By header', async () => {
      const context = createMockContext('/projects');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue('session123');
      Auth.getSessionUser.mockResolvedValue({
        user_id: 'user123',
        username: 'testuser',
        email: 'test@example.com',
      });

      const response = await onRequest(context, next);

      expect(response.headers.delete).toHaveBeenCalledWith('X-Powered-By');
    });

    it('should set HSTS header in production', async () => {
      const originalEnv = process.env.NODE_ENV;
      process.env.NODE_ENV = 'production';

      const context = createMockContext('/projects');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue('session123');
      Auth.getSessionUser.mockResolvedValue({
        user_id: 'user123',
        username: 'testuser',
        email: 'test@example.com',
      });

      const response = await onRequest(context, next);

      expect(response.headers.set).toHaveBeenCalledWith(
        'Strict-Transport-Security',
        'max-age=31536000; includeSubDomains; preload'
      );

      process.env.NODE_ENV = originalEnv;
    });
  });

  describe('Helper Functions', () => {
    describe('getUser', () => {
      it('should return user data for valid session', async () => {
        const request = new Request('http://localhost:3000');
        Auth.getSessionFromRequest.mockResolvedValue('session123');
        Auth.getSessionUser.mockResolvedValue({
          user_id: 'user123',
          username: 'testuser',
          email: 'test@example.com',
        });

        const user = await getUser(request);

        expect(user).toEqual({
          id: 'user123',
          username: 'testuser',
          email: 'test@example.com',
        });
      });

      it('should return null for invalid session', async () => {
        const request = new Request('http://localhost:3000');
        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const user = await getUser(request);

        expect(user).toBeNull();
      });
    });

    describe('getOAuthUser', () => {
      it('should return user data for valid Bearer token', async () => {
        const request = new Request('http://localhost:3000', {
          headers: {
            Authorization: 'Bearer valid-token',
          },
        });

        TodoDB.getAccessToken.mockResolvedValue({
          user_id: 'oauth123',
          username: 'oauthuser',
          email: 'oauth@example.com',
          scopes: '["read","write"]',
          client_id: 'client123',
        });

        const user = await getOAuthUser(request);

        expect(user).toEqual(mockOAuthUser);
      });

      it('should return null for missing Authorization header', async () => {
        const request = new Request('http://localhost:3000');

        const user = await getOAuthUser(request);

        expect(user).toBeNull();
      });

      it('should return null for invalid Bearer token format', async () => {
        const request = new Request('http://localhost:3000', {
          headers: {
            Authorization: 'Basic invalid',
          },
        });

        const user = await getOAuthUser(request);

        expect(user).toBeNull();
      });

      it('should return null for invalid token', async () => {
        const request = new Request('http://localhost:3000', {
          headers: {
            Authorization: 'Bearer invalid-token',
          },
        });

        TodoDB.getAccessToken.mockResolvedValue(null);

        const user = await getOAuthUser(request);

        expect(user).toBeNull();
      });

      it('should handle database errors gracefully', async () => {
        const request = new Request('http://localhost:3000', {
          headers: {
            Authorization: 'Bearer error-token',
          },
        });

        TodoDB.getAccessToken.mockRejectedValue(new Error('Database error'));

        const user = await getOAuthUser(request);

        expect(user).toBeNull();
      });
    });
  });
});
