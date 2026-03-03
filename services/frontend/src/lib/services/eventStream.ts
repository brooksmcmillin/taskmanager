/**
 * SSE client for real-time change events from the backend.
 *
 * Generates a per-tab ID so the backend can tag which browser tab
 * originated a mutation. Handles auto-reconnect with exponential backoff.
 */

import { writable } from 'svelte/store';

export type ConnectionState = 'disconnected' | 'connecting' | 'connected';

export interface ChangeEvent {
	table: string; // "todos" | "projects" | "wiki_pages" | "notifications"
	op: string; // "I" | "U" | "D"
	id: number;
	tab_id: string;
}

// Unique ID for this browser tab — generated once on module load
const TAB_ID = typeof crypto !== 'undefined' ? crypto.randomUUID().slice(0, 8) : '';

export function getTabId(): string {
	return TAB_ID;
}

export const connectionState = writable<ConnectionState>('disconnected');

type ChangeHandler = (event: ChangeEvent) => void;

let eventSource: EventSource | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectAttempt = 0;
const handlers = new Set<ChangeHandler>();
let onReconnectCallback: (() => void) | null = null;

const BASE_DELAY = 1000;
const MAX_DELAY = 30_000;

function getReconnectDelay(): number {
	const delay = Math.min(BASE_DELAY * 2 ** reconnectAttempt, MAX_DELAY);
	reconnectAttempt++;
	return delay;
}

export function onChangeEvent(handler: ChangeHandler): () => void {
	handlers.add(handler);
	return () => handlers.delete(handler);
}

export function setReconnectCallback(cb: () => void): void {
	onReconnectCallback = cb;
}

export function connect(): void {
	if (eventSource) return;

	connectionState.set('connecting');

	const wasReconnect = reconnectAttempt > 0;
	eventSource = new EventSource('/api/events/stream');

	eventSource.onopen = () => {
		connectionState.set('connected');
		reconnectAttempt = 0;
		// On reconnect, reload all stores to catch missed events
		if (wasReconnect && onReconnectCallback) {
			onReconnectCallback();
		}
	};

	eventSource.addEventListener('change', (e: MessageEvent) => {
		try {
			const data: ChangeEvent = JSON.parse(e.data);
			for (const handler of handlers) {
				handler(data);
			}
		} catch {
			// Ignore malformed events
		}
	});

	eventSource.onerror = () => {
		cleanup();
		connectionState.set('connecting');
		const delay = getReconnectDelay();
		reconnectTimer = setTimeout(connect, delay);
	};
}

function cleanup(): void {
	if (eventSource) {
		eventSource.close();
		eventSource = null;
	}
}

export function disconnect(): void {
	if (reconnectTimer) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	cleanup();
	reconnectAttempt = 0;
	connectionState.set('disconnected');
}
