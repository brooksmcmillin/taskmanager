import { writable } from 'svelte/store';

interface ToastAction {
	label: string;
	callback: () => void;
}

interface Toast {
	id: number;
	message: string;
	type: 'success' | 'error' | 'info' | 'warning';
	duration?: number;
	action?: ToastAction;
	href?: string;
}

interface ToastOptions {
	action?: ToastAction;
	href?: string;
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);
	let nextId = 0;

	function show(
		message: string,
		type: Toast['type'] = 'info',
		duration = 3000,
		options?: ToastOptions
	): number {
		const id = nextId++;
		const toast: Toast = { id, message, type, duration, ...options };

		update((toasts) => [...toasts, toast]);

		if (duration > 0) {
			setTimeout(() => {
				update((toasts) => toasts.filter((t) => t.id !== id));
			}, duration);
		}

		return id;
	}

	function dismiss(id: number) {
		update((toasts) => toasts.filter((t) => t.id !== id));
	}

	return {
		subscribe,
		show,
		success: (message: string, duration = 3000, options?: ToastOptions) =>
			show(message, 'success', duration, options),
		error: (message: string, duration = 5000, options?: ToastOptions) =>
			show(message, 'error', duration, options),
		info: (message: string, duration = 3000, options?: ToastOptions) =>
			show(message, 'info', duration, options),
		warning: (message: string, duration = 4000, options?: ToastOptions) =>
			show(message, 'warning', duration, options),
		dismiss,
		clear: () => update(() => [])
	};
}

export const toasts = createToastStore();
export type { Toast, ToastAction, ToastOptions };
