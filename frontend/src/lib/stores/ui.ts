import { writable } from 'svelte/store';

interface Toast {
	id: number;
	message: string;
	type: 'success' | 'error' | 'info' | 'warning';
	duration?: number;
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);
	let nextId = 0;

	return {
		subscribe,
		/**
		 * Display a toast notification
		 * @param message - The message to display
		 * @param type - Type of toast (success, error, info, warning)
		 * @param duration - How long to show the toast in ms (default: 3000)
		 */
		show: (message: string, type: Toast['type'] = 'info', duration = 3000) => {
			const id = nextId++;
			const toast: Toast = { id, message, type, duration };

			update((toasts) => [...toasts, toast]);

			if (duration > 0) {
				setTimeout(() => {
					update((toasts) => toasts.filter((t) => t.id !== id));
				}, duration);
			}
		},
		/**
		 * Display a success toast
		 */
		success: (message: string, duration = 3000) => {
			return createToastStore().show(message, 'success', duration);
		},
		/**
		 * Display an error toast
		 */
		error: (message: string, duration = 5000) => {
			return createToastStore().show(message, 'error', duration);
		},
		/**
		 * Display an info toast
		 */
		info: (message: string, duration = 3000) => {
			return createToastStore().show(message, 'info', duration);
		},
		/**
		 * Display a warning toast
		 */
		warning: (message: string, duration = 4000) => {
			return createToastStore().show(message, 'warning', duration);
		},
		/**
		 * Remove a specific toast by ID
		 */
		dismiss: (id: number) => {
			update((toasts) => toasts.filter((t) => t.id !== id));
		},
		/**
		 * Clear all toasts
		 */
		clear: () => {
			update(() => []);
		}
	};
}

export const toasts = createToastStore();
export type { Toast };
