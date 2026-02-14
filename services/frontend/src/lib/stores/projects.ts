import type { Project, ProjectCreate, ProjectUpdate } from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';
import { createCrudStore } from './createCrudStore';

interface LoadOptions {
	includeStats?: boolean;
	includeArchived?: boolean;
}

function createProjectStore() {
	const store = createCrudStore<Project, ProjectCreate, ProjectUpdate>({
		endpoint: '/api/projects',
		entityName: 'project',
		reorderKey: 'project_ids'
	});

	return {
		subscribe: store.subscribe,
		load: async (options: LoadOptions = {}) => {
			try {
				const params = new URLSearchParams();
				if (options.includeStats) {
					params.set('include_stats', 'true');
				}
				if (options.includeArchived) {
					params.set('include_archived', 'true');
				}
				const url = `/api/projects${params.toString() ? `?${params}` : ''}`;
				const response = await api.get<{ data: Project[]; meta: { count: number } }>(url);
				store.set(response.data || []);
			} catch (error) {
				logger.error('Failed to load projects:', error);
				store.set([]); // Reset to empty on error for consistent UI state
				throw error;
			}
		},
		add: store.add,
		updateProject: store.updateItem,
		remove: store.remove,
		archive: async (id: number) => {
			try {
				const updated = await api.post<{ data: Project }>(`/api/projects/${id}/archive`);
				store.update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to archive project:', error);
				throw error;
			}
		},
		unarchive: async (id: number) => {
			try {
				const updated = await api.post<{ data: Project }>(`/api/projects/${id}/unarchive`);
				store.update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to unarchive project:', error);
				throw error;
			}
		},
		reorder: store.reorder
	};
}

export const projects = createProjectStore();
