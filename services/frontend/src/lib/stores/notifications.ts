import { writable } from 'svelte/store';
import type { NotificationItem } from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

function createNotificationStore() {
	const { subscribe, set, update } = writable<NotificationItem[]>([]);
	const unreadCount = writable<number>(0);

	return {
		subscribe,
		unreadCount,

		load: async (unreadOnly = false) => {
			try {
				const params: Record<string, string> = {};
				if (unreadOnly) params.unread_only = 'true';
				const response = await api.get<{
					data: NotificationItem[];
					meta: { count: number };
				}>('/api/notifications', { params });
				set(response.data || []);
			} catch (error) {
				logger.error('Failed to load notifications:', error);
				throw error;
			}
		},

		loadUnreadCount: async () => {
			try {
				const response = await api.get<{ data: { count: number } }>(
					'/api/notifications/unread-count'
				);
				unreadCount.set(response.data.count);
				return response.data.count;
			} catch (error) {
				logger.error('Failed to load unread count:', error);
				return 0;
			}
		},

		markRead: async (id: number) => {
			try {
				const response = await api.put<{ data: NotificationItem }>(`/api/notifications/${id}/read`);
				update((items) => items.map((n) => (n.id === id ? response.data : n)));
				unreadCount.update((c) => Math.max(0, c - 1));
				return response.data;
			} catch (error) {
				logger.error('Failed to mark notification read:', error);
				throw error;
			}
		},

		markAllRead: async () => {
			try {
				await api.put('/api/notifications/read-all');
				update((items) => items.map((n) => ({ ...n, is_read: true })));
				unreadCount.set(0);
			} catch (error) {
				logger.error('Failed to mark all read:', error);
				throw error;
			}
		},

		remove: async (id: number) => {
			try {
				await api.delete(`/api/notifications/${id}`);
				update((items) => items.filter((n) => n.id !== id));
				// Recalculate unread count
				update((items) => {
					const unread = items.filter((n) => !n.is_read).length;
					unreadCount.set(unread);
					return items;
				});
			} catch (error) {
				logger.error('Failed to delete notification:', error);
				throw error;
			}
		}
	};
}

export const notifications = createNotificationStore();
