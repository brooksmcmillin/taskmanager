import type { RecurringTask, RecurringTaskCreate, RecurringTaskUpdate } from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';
import { createCrudStore } from './createCrudStore';

function createRecurringTaskStore() {
	const store = createCrudStore<RecurringTask, RecurringTaskCreate, RecurringTaskUpdate>({
		endpoint: '/api/recurring-tasks',
		entityName: 'recurring task'
	});

	return {
		subscribe: store.subscribe,
		load: async (activeOnly: boolean = true) => {
			try {
				const params = activeOnly ? { active_only: 'true' } : { active_only: 'false' };
				const response = await api.get<{ data: RecurringTask[]; meta: { count: number } }>(
					'/api/recurring-tasks',
					{ params }
				);
				store.set(response.data || []);
			} catch (error) {
				logger.error('Failed to load recurring tasks:', error);
				throw error;
			}
		},
		add: store.add,
		updateTask: store.updateItem,
		remove: store.remove,
		getById: store.getById
	};
}

export const recurringTasks = createRecurringTaskStore();
