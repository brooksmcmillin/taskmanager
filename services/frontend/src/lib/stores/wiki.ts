import { writable } from 'svelte/store';
import type {
	WikiPage,
	WikiPageSummary,
	WikiPageCreate,
	WikiPageUpdate,
	WikiLinkedTodo,
	WikiTreeNode
} from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

function createWikiStore() {
	const { subscribe, set, update } = writable<WikiPageSummary[]>([]);

	return {
		subscribe,
		set,

		load: async (search?: string, tag?: string) => {
			try {
				const params: Record<string, string> = {};
				if (search) params.q = search;
				if (tag) params.tag = tag;
				const response = await api.get<{ data: WikiPageSummary[]; meta: { count: number } }>(
					'/api/wiki',
					{ params }
				);
				set(response.data || []);
			} catch (error) {
				logger.error('Failed to load wiki pages:', error);
				throw error;
			}
		},

		loadTree: async (): Promise<WikiTreeNode[]> => {
			try {
				const response = await api.get<{ data: WikiTreeNode[] }>('/api/wiki/tree');
				return response.data || [];
			} catch (error) {
				logger.error('Failed to load wiki tree:', error);
				throw error;
			}
		},

		getBySlug: async (slug: string): Promise<WikiPage> => {
			try {
				const response = await api.get<{ data: WikiPage }>(`/api/wiki/${slug}`);
				return response.data;
			} catch (error) {
				logger.error('Failed to get wiki page:', error);
				throw error;
			}
		},

		getById: async (id: number): Promise<WikiPage> => {
			try {
				const response = await api.get<{ data: WikiPage }>(`/api/wiki/${id}`);
				return response.data;
			} catch (error) {
				logger.error('Failed to get wiki page:', error);
				throw error;
			}
		},

		add: async (data: WikiPageCreate): Promise<WikiPage> => {
			try {
				const response = await api.post<{ data: WikiPage }>('/api/wiki', data);
				update((pages) => [
					{
						id: response.data.id,
						title: response.data.title,
						slug: response.data.slug,
						parent_id: response.data.parent_id,
						tags: response.data.tags,
						created_at: response.data.created_at,
						updated_at: response.data.updated_at
					},
					...pages
				]);
				return response.data;
			} catch (error) {
				logger.error('Failed to create wiki page:', error);
				throw error;
			}
		},

		updatePage: async (id: number, data: WikiPageUpdate): Promise<WikiPage> => {
			try {
				const response = await api.put<{ data: WikiPage }>(`/api/wiki/${id}`, data);
				update((pages) =>
					pages.map((p) =>
						p.id === id
							? {
									id: response.data.id,
									title: response.data.title,
									slug: response.data.slug,
									parent_id: response.data.parent_id,
									tags: response.data.tags,
									created_at: response.data.created_at,
									updated_at: response.data.updated_at
								}
							: p
					)
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to update wiki page:', error);
				throw error;
			}
		},

		remove: async (id: number): Promise<void> => {
			try {
				await api.delete(`/api/wiki/${id}`);
				update((pages) => pages.filter((p) => p.id !== id));
			} catch (error) {
				logger.error('Failed to delete wiki page:', error);
				throw error;
			}
		},

		linkTask: async (wikiId: number, todoId: number): Promise<WikiLinkedTodo> => {
			try {
				const response = await api.post<{ data: WikiLinkedTodo }>(`/api/wiki/${wikiId}/link-task`, {
					todo_id: todoId
				});
				return response.data;
			} catch (error) {
				logger.error('Failed to link task:', error);
				throw error;
			}
		},

		unlinkTask: async (wikiId: number, todoId: number): Promise<void> => {
			try {
				await api.delete(`/api/wiki/${wikiId}/link-task/${todoId}`);
			} catch (error) {
				logger.error('Failed to unlink task:', error);
				throw error;
			}
		},

		getLinkedTasks: async (wikiId: number): Promise<WikiLinkedTodo[]> => {
			try {
				const response = await api.get<{ data: WikiLinkedTodo[] }>(
					`/api/wiki/${wikiId}/linked-tasks`
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to get linked tasks:', error);
				throw error;
			}
		},

		resolveLinks: async (titles: string[]): Promise<Record<string, string | null>> => {
			if (titles.length === 0) return {};
			try {
				const response = await api.get<{ data: Record<string, string | null> }>(
					'/api/wiki/resolve',
					{ params: { titles: titles.join(',') } }
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to resolve wiki links:', error);
				return {};
			}
		}
	};
}

export const wiki = createWikiStore();
