/**
 * Routes SSE change events to the appropriate Svelte stores and shows toasts.
 *
 * Own-tab changes are ignored (the store was already updated by the API response).
 * External changes trigger a store reload and an informational toast.
 * Rapid-fire events are debounced so batch operations coalesce into one reload.
 */

import { todos } from '$lib/stores/todos';
import { projects } from '$lib/stores/projects';
import { wiki } from '$lib/stores/wiki';
import { notifications } from '$lib/stores/notifications';
import { toasts } from '$lib/stores/ui';
import {
	getTabId,
	onChangeEvent,
	setReconnectCallback,
	clearReconnectCallback,
	type ChangeEvent
} from './eventStream';

const DEBOUNCE_MS = 300;

const debounceTimers: Record<string, ReturnType<typeof setTimeout>> = {};

function debounce(key: string, fn: () => void): void {
	if (debounceTimers[key]) {
		clearTimeout(debounceTimers[key]);
	}
	debounceTimers[key] = setTimeout(() => {
		delete debounceTimers[key];
		fn();
	}, DEBOUNCE_MS);
}

const OP_LABELS: Record<string, string> = {
	I: 'created',
	U: 'updated',
	D: 'deleted'
};

const TABLE_LABELS: Record<string, string> = {
	todos: 'Task',
	projects: 'Project',
	wiki_pages: 'Wiki page',
	notifications: 'Notification'
};

function handleChangeEvent(event: ChangeEvent): void {
	// Ignore own-tab changes — already reflected in the store
	if (event.tab_id === getTabId()) return;

	const opLabel = OP_LABELS[event.op] || 'changed';
	const tableLabel = TABLE_LABELS[event.table] || 'Record';

	switch (event.table) {
		case 'todos':
			debounce('todos', () => {
				todos.load().catch(() => {});
				toasts.info(`${tableLabel} ${opLabel}`);
			});
			break;

		case 'projects':
			debounce('projects', () => {
				projects.load({ includeStats: true }).catch(() => {});
				toasts.info(`${tableLabel} ${opLabel}`);
			});
			break;

		case 'wiki_pages':
			debounce('wiki_pages', () => {
				wiki.load().catch(() => {});
				toasts.info(`${tableLabel} ${opLabel}`);
			});
			break;

		case 'notifications':
			debounce('notifications', () => {
				notifications.loadUnreadCount().catch(() => {});
				// Only toast for new notifications
				if (event.op === 'I') {
					toasts.info('New notification');
				}
			});
			break;
	}
}

/**
 * Reload all stores — called on SSE reconnect to catch events
 * missed during the disconnect window.
 */
export function reloadAllStores(): void {
	todos.load().catch(() => {});
	projects.load({ includeStats: true }).catch(() => {});
	wiki.load().catch(() => {});
	notifications.loadUnreadCount().catch(() => {});
}

let unsubscribe: (() => void) | null = null;

export function startEventHandlers(): void {
	if (unsubscribe) return;
	unsubscribe = onChangeEvent(handleChangeEvent);
	setReconnectCallback(reloadAllStores);
}

export function stopEventHandlers(): void {
	if (unsubscribe) {
		unsubscribe();
		unsubscribe = null;
	}
	clearReconnectCallback();
	// Clear any pending debounce timers
	for (const key of Object.keys(debounceTimers)) {
		clearTimeout(debounceTimers[key]);
		delete debounceTimers[key];
	}
}
