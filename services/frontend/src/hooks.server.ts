import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

// Use environment variable with fallback to Docker service name
const BACKEND_URL = env.BACKEND_URL || env.VITE_API_URL || 'http://backend:8000';

export const handle: Handle = async ({ event, resolve }) => {
	// Proxy API requests to backend
	if (event.url.pathname.startsWith('/api/')) {
		const backendUrl = `${BACKEND_URL}${event.url.pathname}${event.url.search}`;

		const headers = new Headers(event.request.headers);
		headers.delete('host');
		headers.delete('connection');

		// Build fetch options
		const fetchOptions: RequestInit = {
			method: event.request.method,
			headers
		};

		// Add body for POST/PUT/PATCH requests
		if (event.request.body && ['POST', 'PUT', 'PATCH'].includes(event.request.method)) {
			fetchOptions.body = event.request.body;
			// Required for Node.js fetch with body
			(fetchOptions as any).duplex = 'half';
		}

		const response = await fetch(backendUrl, fetchOptions);

		// Forward all headers from backend (including set-cookie)
		const responseHeaders = new Headers(response.headers);

		return new Response(response.body, {
			status: response.status,
			statusText: response.statusText,
			headers: responseHeaders
		});
	}

	return resolve(event);
};
