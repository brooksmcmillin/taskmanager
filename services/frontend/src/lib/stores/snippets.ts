import { writable } from 'svelte/store';
import { api } from '$lib/api/client';
import type {
	Snippet,
	SnippetSummary,
	SnippetCreate,
	SnippetUpdate,
	CategoryCount
} from '$lib/types';

function createSnippetStore() {
	const { subscribe, set, update } = writable<SnippetSummary[]>([]);

	return {
		subscribe,
		set,

		async load(params?: {
			q?: string;
			category?: string;
			tag?: string;
			date_from?: string;
			date_to?: string;
		}) {
			const result = await api.get<{ data: SnippetSummary[]; meta: { count: number } }>(
				'/api/snippets',
				{ params }
			);
			set(result.data);
			return result;
		},

		async getById(id: number): Promise<Snippet> {
			const result = await api.get<{ data: Snippet }>(`/api/snippets/${id}`);
			return result.data;
		},

		async getCategories(): Promise<CategoryCount[]> {
			const result = await api.get<{ data: CategoryCount[] }>('/api/snippets/categories');
			return result.data;
		},

		async add(data: SnippetCreate): Promise<Snippet> {
			const result = await api.post<{ data: Snippet }>('/api/snippets', data);
			update((items) => [
				{
					id: result.data.id,
					category: result.data.category,
					title: result.data.title,
					snippet_date: result.data.snippet_date,
					tags: result.data.tags,
					created_at: result.data.created_at,
					updated_at: result.data.updated_at
				},
				...items
			]);
			return result.data;
		},

		async updateSnippet(id: number, data: SnippetUpdate): Promise<Snippet> {
			const result = await api.put<{ data: Snippet }>(`/api/snippets/${id}`, data);
			update((items) =>
				items.map((item) =>
					item.id === id
						? {
								id: result.data.id,
								category: result.data.category,
								title: result.data.title,
								snippet_date: result.data.snippet_date,
								tags: result.data.tags,
								created_at: result.data.created_at,
								updated_at: result.data.updated_at
							}
						: item
				)
			);
			return result.data;
		},

		async remove(id: number) {
			await api.delete(`/api/snippets/${id}`);
			update((items) => items.filter((item) => item.id !== id));
		}
	};
}

export const snippets = createSnippetStore();
