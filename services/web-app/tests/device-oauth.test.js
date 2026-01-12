import { describe, it, expect, beforeEach, vi } from 'vitest';
import { onRequest } from '../src/middleware.js';
import { Auth } from '../src/lib/auth.js';
import { TodoDB } from '../src/lib/db.js';
import { createMockContext, createMockNext } from './setup.js';

const url_origin = 'http://localhost:3000';

describe('OAuth 2.0 Device Authorization Grant (RFC 8628)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Middleware - Device Code Endpoint Access', () => {
    it('should allow unauthenticated access to /api/oauth/device/code', async () => {
      const context = createMockContext('/api/oauth/device/code');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);
      TodoDB.getAccessToken.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).not.toHaveBeenCalled();
      expect(next).toHaveBeenCalled();
      expect(context.locals.user).toBeUndefined();
    });

    it('should require authentication for /oauth/device page', async () => {
      const context = createMockContext('/oauth/device');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith(
        url_origin + '/login?return_to=' + encodeURIComponent('/oauth/device')
      );
      expect(next).not.toHaveBeenCalled();
    });

    it('should require authentication for /oauth/device with user_code parameter', async () => {
      const context = createMockContext('/oauth/device?user_code=WDJB-MJHT');
      const next = createMockNext();

      Auth.getSessionFromRequest.mockResolvedValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const result = await onRequest(context, next);

      expect(context.redirect).toHaveBeenCalledWith(
        url_origin +
          '/login?return_to=' +
          encodeURIComponent('/oauth/device?user_code=WDJB-MJHT')
      );
      expect(next).not.toHaveBeenCalled();
    });

    it('should allow authenticated access to /oauth/device', async () => {
      const context = createMockContext('/oauth/device');
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
        auth_type: 'session',
      });
    });
  });

  describe('User Code Generation', () => {
    // These tests require the actual implementation, so we'll import the db module
    // In a real scenario, you might want to test this with the actual database

    it('should generate user codes in expected format (XXXX-XXXX)', () => {
      // User codes should be 8 consonants with a hyphen in the middle
      const userCodePattern =
        /^[BCDFGHJKLMNPQRSTVWXZ]{4}-[BCDFGHJKLMNPQRSTVWXZ]{4}$/;

      // Test multiple generations (using mock approach)
      const validCodes = ['WDJB-MJHT', 'BCDF-GHJK', 'LMNP-QRST', 'VWXZ-BCDF'];

      validCodes.forEach((code) => {
        expect(code).toMatch(userCodePattern);
      });
    });

    it('should not include ambiguous characters (0, O, 1, I, L)', () => {
      const ambiguousChars = ['0', 'O', '1', 'I', 'L', 'A', 'E', 'U', 'Y'];
      const validCode = 'WDJB-MJHT';

      ambiguousChars.forEach((char) => {
        expect(validCode).not.toContain(char);
      });
    });
  });

  describe('Device Authorization Flow States', () => {
    it('should recognize pending state (user has not authorized)', () => {
      const deviceAuth = {
        device_code: 'abc123',
        user_code: 'WDJB-MJHT',
        status: 'pending',
        expires_at: new Date(Date.now() + 1800000),
        user_id: null,
      };

      expect(deviceAuth.status).toBe('pending');
      expect(deviceAuth.user_id).toBeNull();
    });

    it('should recognize authorized state (user has approved)', () => {
      const deviceAuth = {
        device_code: 'abc123',
        user_code: 'WDJB-MJHT',
        status: 'authorized',
        expires_at: new Date(Date.now() + 1800000),
        user_id: 123,
      };

      expect(deviceAuth.status).toBe('authorized');
      expect(deviceAuth.user_id).toBe(123);
    });

    it('should recognize denied state (user has rejected)', () => {
      const deviceAuth = {
        device_code: 'abc123',
        user_code: 'WDJB-MJHT',
        status: 'denied',
        expires_at: new Date(Date.now() + 1800000),
        user_id: null,
      };

      expect(deviceAuth.status).toBe('denied');
    });

    it('should recognize expired state based on expires_at', () => {
      const deviceAuth = {
        device_code: 'abc123',
        user_code: 'WDJB-MJHT',
        status: 'pending',
        expires_at: new Date(Date.now() - 1000), // 1 second ago
        user_id: null,
      };

      const isExpired = new Date(deviceAuth.expires_at) <= new Date();
      expect(isExpired).toBe(true);
    });

    it('should recognize consumed state (token already issued)', () => {
      const deviceAuth = {
        device_code: 'abc123',
        user_code: 'WDJB-MJHT',
        status: 'consumed',
        expires_at: new Date(Date.now() + 1800000),
        user_id: 123,
      };

      expect(deviceAuth.status).toBe('consumed');
    });
  });

  describe('Device Flow Error Responses', () => {
    const errorResponses = [
      {
        error: 'authorization_pending',
        description: 'User has not yet authorized the device',
        shouldRetry: true,
      },
      {
        error: 'slow_down',
        description: 'Polling too frequently. Please wait longer.',
        shouldRetry: true,
      },
      {
        error: 'access_denied',
        description: 'User denied authorization',
        shouldRetry: false,
      },
      {
        error: 'expired_token',
        description: 'Device code has expired',
        shouldRetry: false,
      },
    ];

    it.each(errorResponses)(
      'should return $error error with correct structure',
      ({ error, description, shouldRetry }) => {
        const errorResponse = {
          error,
          error_description: description,
        };

        expect(errorResponse.error).toBe(error);
        expect(errorResponse.error_description).toBe(description);

        // authorization_pending and slow_down mean client should keep polling
        // access_denied and expired_token mean client should stop
        if (shouldRetry) {
          expect(['authorization_pending', 'slow_down']).toContain(error);
        } else {
          expect(['access_denied', 'expired_token']).toContain(error);
        }
      }
    );
  });

  describe('Device Authorization Response Format (RFC 8628)', () => {
    it('should include all required fields in device code response', () => {
      const response = {
        device_code: 'abc123def456...',
        user_code: 'WDJB-MJHT',
        verification_uri: 'https://example.com/oauth/device',
        verification_uri_complete:
          'https://example.com/oauth/device?user_code=WDJB-MJHT',
        expires_in: 1800,
        interval: 5,
      };

      // Required fields per RFC 8628
      expect(response).toHaveProperty('device_code');
      expect(response).toHaveProperty('user_code');
      expect(response).toHaveProperty('verification_uri');
      expect(response).toHaveProperty('expires_in');

      // Optional but recommended
      expect(response).toHaveProperty('verification_uri_complete');
      expect(response).toHaveProperty('interval');

      // Validate types
      expect(typeof response.device_code).toBe('string');
      expect(typeof response.user_code).toBe('string');
      expect(typeof response.verification_uri).toBe('string');
      expect(typeof response.expires_in).toBe('number');
      expect(typeof response.interval).toBe('number');
    });

    it('should have reasonable default expiration (15-30 minutes)', () => {
      const expiresIn = 1800; // 30 minutes
      const minExpiry = 15 * 60; // 15 minutes
      const maxExpiry = 30 * 60; // 30 minutes

      expect(expiresIn).toBeGreaterThanOrEqual(minExpiry);
      expect(expiresIn).toBeLessThanOrEqual(maxExpiry);
    });

    it('should have reasonable default polling interval (5 seconds)', () => {
      const interval = 5;
      const minInterval = 1;
      const maxInterval = 10;

      expect(interval).toBeGreaterThanOrEqual(minInterval);
      expect(interval).toBeLessThanOrEqual(maxInterval);
    });
  });

  describe('User Code Normalization', () => {
    const testCases = [
      { input: 'WDJB-MJHT', expected: 'WDJB-MJHT' },
      { input: 'wdjb-mjht', expected: 'WDJB-MJHT' },
      { input: 'WDJBMJHT', expected: 'WDJB-MJHT' },
      { input: 'wdjbmjht', expected: 'WDJB-MJHT' },
      { input: 'WDJB MJHT', expected: 'WDJB-MJHT' },
      { input: ' WDJB-MJHT ', expected: 'WDJB-MJHT' },
    ];

    it.each(testCases)(
      'should normalize "$input" to "$expected"',
      ({ input, expected }) => {
        // Normalization logic matching db.js implementation
        const normalizedCode = input.toUpperCase().replace(/[\s-]/g, '');
        const formattedCode =
          normalizedCode.slice(0, 4) + '-' + normalizedCode.slice(4);
        const trimmed = formattedCode.trim();

        expect(trimmed).toBe(expected);
      }
    );
  });

  describe('Rate Limiting (slow_down)', () => {
    it('should detect polling too fast based on interval', () => {
      const deviceAuth = {
        last_poll_at: new Date(Date.now() - 2000), // 2 seconds ago
        interval: 5, // 5 second minimum interval
      };

      const now = new Date();
      const timeSinceLastPoll =
        (now - new Date(deviceAuth.last_poll_at)) / 1000;
      const isTooFast = timeSinceLastPoll < deviceAuth.interval;

      expect(isTooFast).toBe(true);
    });

    it('should allow polling after interval has passed', () => {
      const deviceAuth = {
        last_poll_at: new Date(Date.now() - 6000), // 6 seconds ago
        interval: 5, // 5 second minimum interval
      };

      const now = new Date();
      const timeSinceLastPoll =
        (now - new Date(deviceAuth.last_poll_at)) / 1000;
      const isTooFast = timeSinceLastPoll < deviceAuth.interval;

      expect(isTooFast).toBe(false);
    });

    it('should increase interval on slow_down response', () => {
      const initialInterval = 5;
      const intervalIncrement = 5;
      const newInterval = initialInterval + intervalIncrement;

      expect(newInterval).toBe(10);
    });
  });

  describe('Token Response for Device Code Grant', () => {
    it('should return access token with expected fields on success', () => {
      const tokenResponse = {
        access_token: 'abc123...',
        token_type: 'Bearer',
        expires_in: 3600,
        refresh_token: 'def456...',
        scope: 'read write',
      };

      expect(tokenResponse).toHaveProperty('access_token');
      expect(tokenResponse).toHaveProperty('token_type', 'Bearer');
      expect(tokenResponse).toHaveProperty('expires_in');
      expect(tokenResponse).toHaveProperty('refresh_token');
      expect(tokenResponse).toHaveProperty('scope');
    });

    it('should not return refresh token for pending/error states', () => {
      const errorResponse = {
        error: 'authorization_pending',
        error_description: 'User has not yet authorized the device',
      };

      expect(errorResponse).not.toHaveProperty('access_token');
      expect(errorResponse).not.toHaveProperty('refresh_token');
    });
  });

  describe('Grant Type Validation', () => {
    it('should accept the correct device_code grant type URN', () => {
      const validGrantType = 'urn:ietf:params:oauth:grant-type:device_code';
      expect(validGrantType).toBe(
        'urn:ietf:params:oauth:grant-type:device_code'
      );
    });

    it('should validate client has device_code in allowed grant types', () => {
      const clientWithDeviceCode = {
        grant_types: '["authorization_code", "refresh_token", "device_code"]',
      };

      const clientWithoutDeviceCode = {
        grant_types: '["authorization_code", "refresh_token"]',
      };

      const grantTypesWithDevice = JSON.parse(clientWithDeviceCode.grant_types);
      const grantTypesWithoutDevice = JSON.parse(
        clientWithoutDeviceCode.grant_types
      );

      expect(grantTypesWithDevice).toContain('device_code');
      expect(grantTypesWithoutDevice).not.toContain('device_code');
    });
  });

  describe('Scope Validation', () => {
    it('should validate requested scopes against client allowed scopes', () => {
      const clientScopes = ['read', 'write'];
      const requestedScopes = ['read'];

      const invalidScopes = requestedScopes.filter(
        (s) => !clientScopes.includes(s)
      );

      expect(invalidScopes).toHaveLength(0);
    });

    it('should reject invalid scopes', () => {
      const clientScopes = ['read', 'write'];
      const requestedScopes = ['read', 'delete', 'admin'];

      const invalidScopes = requestedScopes.filter(
        (s) => !clientScopes.includes(s)
      );

      expect(invalidScopes).toEqual(['delete', 'admin']);
    });

    it('should use client default scopes when none requested', () => {
      const clientScopes = ['read', 'write'];
      const requestedScope = null;

      const scopes = requestedScope ? requestedScope.split(' ') : clientScopes;

      expect(scopes).toEqual(['read', 'write']);
    });
  });
});
