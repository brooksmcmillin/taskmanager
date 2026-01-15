import { browser } from '$app/environment';
import { goto } from '$app/navigation';
import type { ApiResponse } from '$lib/types';

const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiClient {
	private async request<T>(
		method: string,
		path: string,
		options: { body?: unknown; params?: Record<string, string> } = {}
	): Promise<T> {
		const url = new URL(`${BASE_URL}${path}`, window.location.origin);

		if (options.params) {
			Object.entries(options.params).forEach(([key, value]) => {
				if (value) url.searchParams.set(key, value);
			});
		}

		const response = await fetch(url.toString(), {
			method,
			headers: {
				'Content-Type': 'application/json'
			},
			credentials: 'include',
			body: options.body ? JSON.stringify(options.body) : undefined
		});

		if (response.status === 401) {
			if (browser) goto('/login');
			throw new Error('Authentication required');
		}

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail?.message || error.error?.message || 'Request failed');
		}

		return response.json();
	}

	get<T>(path: string, options?: { params?: Record<string, string> }) {
		return this.request<T>('GET', path, options);
	}

	post<T>(path: string, body?: unknown) {
		return this.request<T>('POST', path, { body });
	}

	put<T>(path: string, body?: unknown) {
		return this.request<T>('PUT', path, { body });
	}

	delete<T>(path: string) {
		return this.request<T>('DELETE', path);
	}
}

export const api = new ApiClient();
