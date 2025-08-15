import { describe, it, expect, beforeEach, vi } from 'vitest';
import { onRequest } from '../src/middleware.js';
import { Auth } from '../src/lib/auth.js';
import { TodoDB } from '../src/lib/db.js';
import { createMockContext, createMockNext } from './setup.js';

describe('Page Route Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Protected Page Routes', () => {
    const protectedPageRoutes = [
      { path: '/', name: 'Home page' },
      { path: '/projects', name: 'Projects page' },
      { path: '/register', name: 'Register page' },
      { path: '/oauth/authorize', name: 'OAuth authorize page' },
    ];

    it.each(protectedPageRoutes)(
      'should redirect unauthenticated users from $name',
      async ({ path }) => {
        const context = createMockContext(path);
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
        expect(next).not.toHaveBeenCalled();
      }
    );

    it.each(protectedPageRoutes)(
      'should allow authenticated users to access $name',
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

  describe('Unprotected Page Routes', () => {
    const unprotectedPageRoutes = [{ path: '/login', name: 'Login page' }];

    it.each(unprotectedPageRoutes)(
      'should redirect unauthenticated users from $name (current bug)',
      async ({ path }) => {
        const context = createMockContext(path);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);
        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toBeUndefined();
      }
    );

    it.each(unprotectedPageRoutes)(
      'should not redirect authenticated users from $name',
      async ({ path }) => {
        const context = createMockContext(path);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue('session123');
        Auth.getSessionUser.mockResolvedValue({
          user_id: 'user123',
          username: 'testuser',
          email: 'test@example.com',
        });

        const result = await onRequest(context, next);

        expect(context.redirect).not.toHaveBeenCalled();
        expect(next).toHaveBeenCalled();
        expect(context.locals.user).toBeUndefined();
      }
    );
  });

  describe('Static Asset Routes', () => {
    it('should not redirect unauthenticated access to CSS files', async () => {
      const context = createMockContext('/src/styles/global.css');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).not.toHaveBeenCalled();
      expect(next).toHaveBeenCalled();
      expect(context.locals.user).toBeUndefined();
    });

    it('should redirect unauthenticated access to other CSS files', async () => {
      const context = createMockContext('/src/styles/components/button.css');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith('/login');
      expect(next).not.toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle trailing slashes in protected routes', async () => {
      const context = createMockContext('/projects/');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith('/login');
    });

    it('should handle query parameters in protected routes', async () => {
      const context = createMockContext('/projects?filter=active');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith('/login');
    });

    it('should handle hash fragments in protected routes', async () => {
      const context = createMockContext('/projects#section1');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith('/login');
    });

    it('should handle nested protected routes', async () => {
      const context = createMockContext('/projects/123/details');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith('/login');
    });
  });
});

