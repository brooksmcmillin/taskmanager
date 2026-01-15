import type { LayoutServerLoad } from './$types';

const BACKEND_URL = 'http://backend:8000';

export const load: LayoutServerLoad = async ({ cookies, url }) => {
	const sessionId = cookies.get('session');

	// Public routes that don't require auth
	const publicRoutes = ['/login', '/register'];
	const isPublicRoute = publicRoutes.includes(url.pathname);

	// If no session and not on public route, user will be null (client will redirect)
	if (!sessionId) {
		return { user: null };
	}

	try {
		// Check session with backend
		const response = await fetch(`${BACKEND_URL}/api/auth/session`, {
			headers: {
				Cookie: `session=${sessionId}`
			}
		});

		if (response.ok) {
			const data = await response.json();
			return { user: data.user };
		}
	} catch (error) {
		console.error('Failed to verify session:', error);
	}

	return { user: null };
};
