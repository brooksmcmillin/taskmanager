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
}

function createToastStore() {
	const { subscribe, update } = writable<Toast[]>([]);
	let nextId = 0;

	function show(
		message: string,
		type: Toast['type'] = 'info',
		duration = 3000,
		action?: ToastAction
	): number {
		const id = nextId++;
		const toast: Toast = { id, message, type, duration, action };

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
		success: (message: string, duration = 3000, action?: ToastAction) =>
			show(message, 'success', duration, action),
		error: (message: string, duration = 5000) => show(message, 'error', duration),
		info: (message: string, duration = 3000) => show(message, 'info', duration),
		warning: (message: string, duration = 4000) => show(message, 'warning', duration),
		dismiss,
		clear: () => update(() => [])
	};
}

export const toasts = createToastStore();
export type { Toast, ToastAction };
