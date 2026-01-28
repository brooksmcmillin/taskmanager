import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';
import { logger } from '$lib/utils/logger';

// Use environment variable with fallback to Docker service name
const BACKEND_URL = env.BACKEND_URL || env.VITE_API_URL || 'http://backend:8000';
logger.info(`[Hooks] BACKEND_URL configured as: ${BACKEND_URL}`);

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

	return resolve(event);
};
