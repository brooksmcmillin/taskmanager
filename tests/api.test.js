import { describe, it, expect, beforeEach, vi } from 'vitest';
import { onRequest } from '../src/middleware.js';
import { Auth } from '../src/lib/auth.js';
import { TodoDB } from '../src/lib/db.js';
import { createMockContext, createMockNext } from './setup.js';

const url_origin = "http://localhost:3000"

describe('API Route Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Protected API Routes', () => {
    const protectedApiRoutes = [
      { path: '/api/projects', name: 'Projects API' },
      { path: '/api/projects/123', name: 'Single project API' },
      { path: '/api/todos', name: 'Todos API' },
      { path: '/api/todos/456', name: 'Single todo API' },
      { path: '/api/todos/456/complete', name: 'Complete todo API' },
      { path: '/api/categories', name: 'Categories API' },
      { path: '/api/tasks/search', name: 'Tasks search API' },
      { path: '/api/auth/logout', name: 'Logout API' },
      // { path: '/api/auth/register', name: 'Register API' },
      { path: '/api/oauth/clients', name: 'OAuth clients API' },
      { path: '/api/oauth/jwks', name: 'OAuth JWKS API' },
    ];

    it.each(protectedApiRoutes)(
      'should redirect unauthenticated requests to $name',
      async ({ path }) => {
        const context = createMockContext(path);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith(url_origin + '/login?return_to=' + encodeURIComponent(path));
        expect(result).toEqual({
          type: 'redirect',
          status: 302,
          url: url_origin + '/login?return_to=' + encodeURIComponent(path),
        });
        expect(next).not.toHaveBeenCalled();
      }
    );

    it.each(protectedApiRoutes)(
      'should allow authenticated requests to $name',
      async ({ path }) => {
        const context = createMockContext(path);
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
      }
    );
  });

  describe('Unprotected API Routes', () => {
    it('should not redirect unauthenticated access to login endpoint', async () => {
      const context = createMockContext('/api/auth/login');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).not.toHaveBeenCalled();
      expect(next).toHaveBeenCalled();
      expect(context.locals.user).toBeUndefined();
    });

    it('should not redirect unauthenticated access to OAuth token endpoint', async () => {
      const context = createMockContext('/api/oauth/token');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);
      TodoDB.getAccessToken.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).not.toHaveBeenCalled();
      expect(next).toHaveBeenCalled();
      expect(context.locals.user).toBeUndefined();
    });
  });

  /*describe('OAuth Bearer Token Authentication', () => {
    const oauthProtectedRoutes = [
      { path: '/api/oauth/authorize', name: 'OAuth authorize' },
      { path: '/api/oauth/token', name: 'OAuth token' },
    ];

    /* it.each(oauthProtectedRoutes)(
      'should authenticate $name with valid Bearer token',
      async ({ path }) => {
        const context = createMockContext(path, {
          Authorization: 'Bearer valid-token-123',
        });
        const next = createMockNext();

        TodoDB.getAccessToken.mockResolvedValue({
          user_id: 'oauth-user-123',
          username: 'oauthuser',
          email: 'oauth@example.com',
          scopes: '["read","write"]',
          client_id: 'client-app-123',
        });

        const response = await onRequest(context, next);

        expect(TodoDB.getAccessToken).toHaveBeenCalledWith('valid-token-123');
        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toEqual({
          id: 'oauth-user-123',
          username: 'oauthuser',
          email: 'oauth@example.com',
          scopes: ['read', 'write'],
          clientId: 'client-app-123',
        });
      }
    ); */

    /*it('should redirect OAuth routes with invalid Bearer token', async () => {
      const context = createMockContext('/api/oauth/authorize', {
        Authorization: 'Bearer invalid-token',
      });
      const next = createMockNext();

      TodoDB.getAccessToken.mockResolvedValue(null);
      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(TodoDB.getAccessToken).toHaveBeenCalledWith('invalid-token');
      expect(context.redirect).toHaveBeenCalledWith('/login');
      expect(result).toEqual({
        type: 'redirect',
        status: 302,
        url: '/login',
      });
    });*/

    /*it('should redirect OAuth routes without Bearer token', async () => {
      const context = createMockContext('/api/oauth/authorize');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(TodoDB.getAccessToken).not.toHaveBeenCalled();
        expect(context.redirect).toHaveBeenCalledWith('/login');
      expect(context.redirect).toHaveBeenCalledWith('/login');
    });*/

    /*it('should handle malformed Authorization headers', async () => {
      const malformedHeaders = [
        { Authorization: 'Bearer' },
        { Authorization: 'Basic dXNlcjpwYXNz' },
        { Authorization: 'InvalidScheme token123' },
        { Authorization: '   Bearer   ' },
      ];

      for (const headers of malformedHeaders) {
        const context = createMockContext('/api/oauth/authorize', headers);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith(url_origin + '/login?return_to=' + encodeURIComponent('/api/oauth/authorize'));
      }
    });*/
  //});*/

  describe('Mixed Authentication Scenarios', () => {
    it('should prefer OAuth token over session for OAuth routes', async () => {
      // Use /api/oauth/userinfo which is the correct OAuth-protected endpoint
      // (not /api/oauth/authorize which uses session auth to grant tokens)
      const context = createMockContext('/api/oauth/userinfo', {
        Authorization: 'Bearer oauth-token',
      });
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue('session123');
      Auth.getSessionUser.mockResolvedValue({
        user_id: 'session-user',
        username: 'sessionuser',
        email: 'session@example.com',
      });

      TodoDB.getAccessToken.mockResolvedValue({
        user_id: 'oauth-user',
        username: 'oauthuser',
        email: 'oauth@example.com',
        scopes: '["admin"]',
        client_id: 'admin-client',
      });

      const response = await onRequest(context, next);

      expect(context.locals.user).toEqual({
        id: 'oauth-user',
        username: 'oauthuser',
        email: 'oauth@example.com',
        scopes: ['admin'],
        clientId: 'admin-client',
      });
      expect(next).toHaveBeenCalled();
    });

    it('should use session authentication for regular API routes', async () => {
      const context = createMockContext('/api/todos');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue('session123');
      Auth.getSessionUser.mockResolvedValue({
        user_id: 'user123',
        username: 'testuser',
        email: 'test@example.com',
      });

      const response = await onRequest(context, next);

      expect(TodoDB.getAccessToken).not.toHaveBeenCalled();
      expect(context.locals.user).toEqual({
        id: 'user123',
        username: 'testuser',
        email: 'test@example.com',
      });
      expect(next).toHaveBeenCalled();
    });
  });

  describe('HTTP Methods', () => {
    const httpMethods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'];

    it.each(httpMethods)(
      'should enforce authentication for %s requests',
      async (method) => {
        const context = createMockContext('/api/todos');
        context.request = new Request('http://localhost:3000/api/todos', {
          method,
        });
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith(url_origin + '/login?return_to=' + encodeURIComponent('/api/todos'));
      }
    );
  });
});

