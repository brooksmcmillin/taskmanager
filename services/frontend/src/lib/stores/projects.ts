import { writable } from 'svelte/store';
import type { Project, ProjectCreate, ProjectUpdate } from '$lib/types';
import { api } from '$lib/api/client';

function createProjectStore() {
	const { subscribe, set, update } = writable<Project[]>([]);

	return {
		subscribe,
		load: async () => {
			try {
				const response = await api.get<{ data: Project[]; meta: { count: number } }>('/api/projects');
				set(response.data || []);
			} catch (error) {
				console.error('Failed to load projects:', error);
				throw error;
			}
		},
		add: async (project: ProjectCreate) => {
			try {
				const created = await api.post<{ data: Project }>('/api/projects', project);
				update((projects) => [...projects, created.data]);
				return created.data;
			} catch (error) {
				console.error('Failed to add project:', error);
				throw error;
			}
		},
		updateProject: async (id: number, updates: ProjectUpdate) => {
			try {
				const updated = await api.put<{ data: Project }>(`/api/projects/${id}`, updates);
				update((projects) => projects.map((p) => (p.id === id ? updated.data : p)));
				return updated.data;
			} catch (error) {
				console.error('Failed to update project:', error);
				throw error;
			}
		},
		remove: async (id: number) => {
			try {
				await api.delete(`/api/projects/${id}`);
				update((projects) => projects.filter((p) => p.id !== id));
			} catch (error) {
				console.error('Failed to remove project:', error);
				throw error;
			}
		}
	};
}

export const projects = createProjectStore();
