import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { logger } from '$lib/utils/logger';

// Use environment variable with fallback to Docker service name
const BACKEND_URL = env.BACKEND_URL || env.VITE_API_URL || 'http://backend:8000';
logger.info(`[Hooks] BACKEND_URL configured as: ${BACKEND_URL}`);

/**
 * Security headers applied to all SvelteKit responses.
 *
 * CSP allows:
 * - 'self': same-origin scripts, styles, images, fonts, etc.
 * - 'unsafe-inline' for style-src: SvelteKit injects inline styles for SSR.
 * - data: for img-src: some icons/assets use data URIs.
 * - connect-src 'self': XHR/fetch to same origin (API proxy).
 */
const SECURITY_HEADERS: Record<string, string> = {
	'X-Content-Type-Options': 'nosniff',
	'X-Frame-Options': 'DENY',
	'Referrer-Policy': 'strict-origin-when-cross-origin',
	'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
	'Content-Security-Policy': [
		"default-src 'self'",
		"script-src 'self' 'unsafe-inline'",
		"style-src 'self' 'unsafe-inline'",
		"img-src 'self' data:",
		"font-src 'self'",
		"connect-src 'self'",
		"frame-ancestors 'none'",
		"base-uri 'self'",
		"form-action 'self'"
	].join('; '),
	'Permissions-Policy':
		'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()'
};

export const handle: Handle = async ({ event, resolve }) => {
	// Proxy API requests to backend
	if (event.url.pathname.startsWith('/api/')) {
		const backendUrl = `${BACKEND_URL}${event.url.pathname}${event.url.search}`;
		logger.debug(`[Proxy] ${event.request.method} ${event.url.pathname} -> ${backendUrl}`);

		const headers = new Headers(event.request.headers);
		headers.delete('host');
		headers.delete('connection');

		// Build fetch options
		const fetchOptions: RequestInit = {
			method: event.request.method,
			headers,
			redirect: 'manual' // Don't follow redirects automatically
		};

		// Add body for POST/PUT/PATCH requests
		if (event.request.body && ['POST', 'PUT', 'PATCH'].includes(event.request.method)) {
			fetchOptions.body = event.request.body;
			// Required for Node.js fetch with body
			(fetchOptions as any).duplex = 'half';
		}

		try {
			const response = await fetch(backendUrl, fetchOptions);

			// Handle redirects properly
			if (response.status >= 300 && response.status < 400) {
				const location = response.headers.get('location');
				if (location) {
					// Return redirect response with all headers (including set-cookie)
					const responseHeaders = new Headers(response.headers);
					return new Response(null, {
						status: response.status,
						headers: responseHeaders
					});
				}
			}

			return new Response(response.body, {
				status: response.status,
				statusText: response.statusText,
				headers: response.headers
			});
		} catch (error) {
			logger.error(`[Proxy] Error proxying to ${backendUrl}:`, error);
			return new Response(JSON.stringify({ error: 'Backend request failed' }), {
				status: 502,
				headers: { 'Content-Type': 'application/json' }
			});
		}
	}

	const response = await resolve(event);

	// Apply security headers to all non-proxied responses
	for (const [header, value] of Object.entries(SECURITY_HEADERS)) {
		response.headers.set(header, value);
	}

	return response;
};
