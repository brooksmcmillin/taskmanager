import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

interface CrudStoreConfig {
	endpoint: string;
	entityName: string;
	reorderKey?: string;
}

export function createCrudStore<T extends { id: number; position?: number }, TCreate, TUpdate>(
	config: CrudStoreConfig
) {
	const { subscribe, set, update } = writable<T[]>([]);

	return {
		subscribe,
		set,
		update,
		add: async (data: TCreate): Promise<T> => {
			try {
				const created = await api.post<{ data: T }>(config.endpoint, data);
				update((items) => [...items, created.data]);
				return created.data;
			} catch (error) {
				logger.error(`Failed to add ${config.entityName}:`, error);
				throw error;
			}
		},
		updateItem: async (id: number, data: TUpdate): Promise<T> => {
			try {
				const updated = await api.put<{ data: T }>(`${config.endpoint}/${id}`, data);
				update((items) => items.map((item) => (item.id === id ? updated.data : item)));
				return updated.data;
			} catch (error) {
				logger.error(`Failed to update ${config.entityName}:`, error);
				throw error;
			}
		},
		remove: async (id: number): Promise<void> => {
			try {
				await api.delete(`${config.endpoint}/${id}`);
				update((items) => items.filter((item) => item.id !== id));
			} catch (error) {
				logger.error(`Failed to remove ${config.entityName}:`, error);
				throw error;
			}
		},
		getById: async (id: number): Promise<T> => {
			try {
				const response = await api.get<{ data: T }>(`${config.endpoint}/${id}`);
				return response.data;
			} catch (error) {
				logger.error(`Failed to get ${config.entityName}:`, error);
				throw error;
			}
		},
		reorder: async (ids: number[]): Promise<void> => {
			try {
				const key = config.reorderKey ?? `${config.entityName}_ids`;
				await api.post(`${config.endpoint}/reorder`, { [key]: ids });
				update((items) => {
					const itemMap = new Map(items.map((item) => [item.id, item]));
					const reordered: T[] = [];
					ids.forEach((id, index) => {
						const item = itemMap.get(id);
						if (item) {
							reordered.push({ ...item, position: index } as T);
						}
					});
					return reordered.concat(items.filter((item) => !ids.includes(item.id)));
				});
			} catch (error) {
				logger.error(`Failed to reorder ${config.entityName}s:`, error);
				throw error;
			}
		}
	};
}
