import { writable, derived } from 'svelte/store';
import type { Todo, TodoFilters, TodoCreate, TodoUpdate } from '$lib/types';
import { api } from '$lib/api/client';

function createTodoStore() {
	const { subscribe, set, update } = writable<Todo[]>([]);

	return {
		subscribe,
		load: async (filters?: TodoFilters) => {
			try {
				// Convert filter values to strings properly
				const params = filters
					? (Object.fromEntries(
							Object.entries(filters)
								.filter(([, value]) => value !== undefined)
								.map(([key, value]) => [key, String(value)])
						) as Record<string, string>)
					: undefined;

				const response = await api.get<{ data: Todo[]; meta: { count: number } }>('/api/todos', {
					params
				});
				set(response.data || []);
			} catch (error) {
				console.error('Failed to load todos:', error);
				throw error;
			}
		},
		add: async (todo: TodoCreate) => {
			try {
				const created = await api.post<{ data: Todo }>('/api/todos', todo);
				update((todos) => [...todos, created.data]);
				return created.data;
			} catch (error) {
				console.error('Failed to add todo:', error);
				throw error;
			}
		},
		updateTodo: async (id: number, updates: TodoUpdate) => {
			try {
				const updated = await api.put<{ data: Todo }>(`/api/todos/${id}`, updates);
				update((todos) => todos.map((t) => (t.id === id ? updated.data : t)));
				return updated.data;
			} catch (error) {
				console.error('Failed to update todo:', error);
				throw error;
			}
		},
		complete: async (id: number) => {
			try {
				await api.post(`/api/todos/${id}/complete`, {});
				update((todos) =>
					todos.map((t) => (t.id === id ? { ...t, status: 'completed' as const } : t))
				);
			} catch (error) {
				console.error('Failed to complete todo:', error);
				throw error;
			}
		},
		remove: async (id: number) => {
			try {
				await api.delete(`/api/todos/${id}`);
				update((todos) => todos.filter((t) => t.id !== id));
			} catch (error) {
				console.error('Failed to remove todo:', error);
				throw error;
			}
		},
		getById: async (id: number): Promise<Todo> => {
			try {
				const response = await api.get<{ data: Todo }>(`/api/todos/${id}`);
				return response.data;
			} catch (error) {
				console.error('Failed to get todo:', error);
				throw error;
			}
		}
	};
}

export const todos = createTodoStore();

export const pendingTodos = derived(todos, ($todos) =>
	$todos.filter((t) => t.status === 'pending')
);

export const completedTodos = derived(todos, ($todos) =>
	$todos.filter((t) => t.status === 'completed')
);

export const todosByProject = derived(todos, ($todos) => {
	const grouped: Record<number, Todo[]> = {};
	$todos.forEach((t) => {
		const pid = t.project_id || 0;
		if (!grouped[pid]) grouped[pid] = [];
		grouped[pid].push(t);
	});
	return grouped;
});
