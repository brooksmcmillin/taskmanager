import { vi } from 'vitest';

global.fetch = vi.fn();

vi.mock('astro:middleware', () => ({
  defineMiddleware: (fn) => fn,
}));

vi.mock('../src/lib/auth.js', () => ({
  Auth: {
    getSessionFromRequest: vi.fn(),
    getSessionUser: vi.fn(),
  },
}));

vi.mock('../src/lib/db.js', () => ({
  TodoDB: {
    getAccessToken: vi.fn(),
  },
}));

export const createMockContext = (pathname = '/', headers = {}) => {
  const request = new Request(`http://localhost:3000${pathname}`, {
    headers: new Headers(headers),
  });

  return {
    request,
    url: new URL(request.url),
    redirect: vi.fn((path) => ({
      type: 'redirect',
      status: 302,
      url: path,
    })),
    locals: {},
  };
};

export const createMockNext = () => {
  return vi.fn(() => {
    const headers = new Map([['Content-Type', 'text/html']]);

    return Promise.resolve({
      headers: {
        set: vi.fn((key, value) => headers.set(key, value)),
        get: vi.fn((key) => headers.get(key)),
        delete: vi.fn((key) => headers.delete(key)),
      },
    });
  });
};

export const mockAuthenticatedUser = {
  id: 'user123',
  username: 'testuser',
  email: 'test@example.com',
};

export const mockOAuthUser = {
  id: 'oauth123',
  username: 'oauthuser',
  email: 'oauth@example.com',
  scopes: ['read', 'write'],
  clientId: 'client123',
};
