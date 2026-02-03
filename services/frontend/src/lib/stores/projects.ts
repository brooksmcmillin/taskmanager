import { writable } from 'svelte/store';
import type { Project, ProjectCreate, ProjectUpdate } from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

interface LoadOptions {
	includeStats?: boolean;
	includeArchived?: boolean;
}

function createProjectStore() {
	const { subscribe, set, update } = writable<Project[]>([]);

	return {
		subscribe,
		load: async (options: LoadOptions = {}) => {
			try {
				const params = new URLSearchParams();
				if (options.includeStats) {
					params.set('include_stats', 'true');
				}
				if (options.includeArchived) {
					params.set('include_archived', 'true');
				}
				const queryString = params.toString();
				const url = queryString ? `/api/projects?${queryString}` : '/api/projects';
				const response = await api.get<{ data: Project[]; meta: { count: number } }>(url);
				set(response.data || []);
			} catch (error) {
				logger.error('Failed to load projects:', error);
				throw error;
			}
		},
		add: async (project: ProjectCreate) => {
			try {
				const created = await api.post<{ data: Project }>('/api/projects', project);
				update((projects) => [...projects, created.data]);
				return created.data;
			} catch (error) {
				logger.error('Failed to add project:', error);
				throw error;
			}
		},
		updateProject: async (id: number, updates: ProjectUpdate) => {
			try {
				const updated = await api.put<{ data: Project }>(`/api/projects/${id}`, updates);
				update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to update project:', error);
				throw error;
			}
		},
		remove: async (id: number) => {
			try {
				await api.delete(`/api/projects/${id}`);
				update((projects) => projects.filter((p) => p.id !== id));
			} catch (error) {
				logger.error('Failed to remove project:', error);
				throw error;
			}
		},
		archive: async (id: number) => {
			try {
				const updated = await api.post<{ data: Project }>(`/api/projects/${id}/archive`);
				update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to archive project:', error);
				throw error;
			}
		},
		unarchive: async (id: number) => {
			try {
				const updated = await api.post<{ data: Project }>(`/api/projects/${id}/unarchive`);
				update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to unarchive project:', error);
				throw error;
			}
		},
		reorder: async (projectIds: number[]) => {
			try {
				await api.post('/api/projects/reorder', { project_ids: projectIds });
				// Update local positions
				update((projects) => {
					const projectMap = new Map(projects.map((p) => [p.id, p]));
					return projectIds
						.map((id, index) => {
							const project = projectMap.get(id);
							if (project) {
								return { ...project, position: index };
							}
							return null;
						})
						.filter((p): p is Project => p !== null)
						.concat(projects.filter((p) => !projectIds.includes(p.id)));
				});
			} catch (error) {
				logger.error('Failed to reorder projects:', error);
				throw error;
			}
		}
	};
}

export const projects = createProjectStore();
