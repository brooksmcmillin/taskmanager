import { describe, it, expect, beforeEach, vi } from 'vitest';
import { onRequest } from '../src/middleware.js';
import { Auth } from '../src/lib/auth.js';
import { TodoDB } from '../src/lib/db.js';
import { createMockContext, createMockNext } from './setup.js';

const url_origin = 'http://localhost:3000';

describe('Page Route Authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Protected Page Routes', () => {
    const protectedPageRoutes = [
      { path: '/', name: 'Home page' },
      { path: '/projects', name: 'Projects page' },
    ];

    it.each(protectedPageRoutes)(
      'should redirect unauthenticated users from $name',
      async ({ path }) => {
        const context = createMockContext(path);
        const next = createMockNext();

        Auth.getSessionFromRequest.mockResolvedValue(null);
        Auth.getSessionUser.mockResolvedValue(null);

        const result = await onRequest(context, next);

        expect(context.redirect).toHaveBeenCalledWith(
          url_origin + '/login?return_to=' + encodeURIComponent(path)
        );
        expect(result).toEqual({
          type: 'redirect',
          status: 302,
          url: url_origin + '/login?return_to=' + encodeURIComponent(path),
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

    it.each([
      ['should handle nested protected routes', '/projects/123/details'],
      // ['should handle hash fragments in protected routes', '/projects#section1'], // TODO: Fix this and uncomment the test
      [
        'should handle query parameters in proteced routes',
        '/projects?fiter=active',
      ],
      ['should handle trailing slashes in protected routes', '/projects/'],
      [
        'should redirect unauthenticated access to other CSS files',
        '/src/styles/components/button.css',
      ],
    ])('%s', async (description, route) => {
      const context = createMockContext(route);
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith(
        url_origin + '/login?return_to=' + encodeURIComponent(route)
      );
    });
  });
});
