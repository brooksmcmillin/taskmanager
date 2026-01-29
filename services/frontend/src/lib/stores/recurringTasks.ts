import { writable } from 'svelte/store';
import type { RecurringTask, RecurringTaskCreate, RecurringTaskUpdate } from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

function createRecurringTaskStore() {
	const { subscribe, set, update } = writable<RecurringTask[]>([]);

	return {
		subscribe,
		load: async (activeOnly: boolean = true) => {
			try {
				const params = activeOnly ? { active_only: 'true' } : { active_only: 'false' };
				const response = await api.get<{ data: RecurringTask[]; meta: { count: number } }>(
					'/api/recurring-tasks',
					{ params }
				);
				set(response.data || []);
			} catch (error) {
				logger.error('Failed to load recurring tasks:', error);
				throw error;
			}
		},
		add: async (task: RecurringTaskCreate) => {
			try {
				const created = await api.post<{ data: RecurringTask }>('/api/recurring-tasks', task);
				update((tasks) => [...tasks, created.data]);
				return created.data;
			} catch (error) {
				logger.error('Failed to add recurring task:', error);
				throw error;
			}
		},
		updateTask: async (id: number, updates: RecurringTaskUpdate) => {
			try {
				const updated = await api.put<{ data: RecurringTask }>(
					`/api/recurring-tasks/${id}`,
					updates
				);
				update((tasks) => tasks.map((t) => (t.id === id ? updated.data : t)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to update recurring task:', error);
				throw error;
			}
		},
		remove: async (id: number) => {
			try {
				await api.delete(`/api/recurring-tasks/${id}`);
				update((tasks) => tasks.filter((t) => t.id !== id));
			} catch (error) {
				logger.error('Failed to remove recurring task:', error);
				throw error;
			}
		},
		getById: async (id: number): Promise<RecurringTask> => {
			try {
				const response = await api.get<{ data: RecurringTask }>(`/api/recurring-tasks/${id}`);
				return response.data;
			} catch (error) {
				logger.error('Failed to get recurring task:', error);
				throw error;
			}
		}
	};
}

export const recurringTasks = createRecurringTaskStore();
