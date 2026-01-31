import { writable, derived } from 'svelte/store';
import type {
	Todo,
	TodoFilters,
	TodoCreate,
	TodoUpdate,
	Subtask,
	SubtaskCreate,
	Attachment
} from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';

function createTodoStore() {
	const { subscribe, set, update } = writable<Todo[]>([]);

	return {
		subscribe,
		load: async (filters?: TodoFilters & { include_subtasks?: boolean }) => {
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
				logger.error('Failed to load todos:', error);
				throw error;
			}
		},
		add: async (todo: TodoCreate) => {
			try {
				const created = await api.post<{ data: Todo }>('/api/todos', todo);
				update((todos) => [...todos, created.data]);
				return created.data;
			} catch (error) {
				logger.error('Failed to add todo:', error);
				throw error;
			}
		},
		updateTodo: async (id: number, updates: TodoUpdate) => {
			try {
				const updated = await api.put<{ data: Todo }>(`/api/todos/${id}`, updates);
				update((todos) => todos.map((t) => (t.id === id ? updated.data : t)));
				return updated.data;
			} catch (error) {
				logger.error('Failed to update todo:', error);
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
				logger.error('Failed to complete todo:', error);
				throw error;
			}
		},
		remove: async (id: number) => {
			try {
				await api.delete(`/api/todos/${id}`);
				update((todos) => todos.filter((t) => t.id !== id));
			} catch (error) {
				logger.error('Failed to remove todo:', error);
				throw error;
			}
		},
		getById: async (id: number): Promise<Todo> => {
			try {
				const response = await api.get<{ data: Todo }>(`/api/todos/${id}`);
				return response.data;
			} catch (error) {
				logger.error('Failed to get todo:', error);
				throw error;
			}
		},
		// Subtask methods
		addSubtask: async (todoId: number, subtask: SubtaskCreate): Promise<Subtask> => {
			try {
				const response = await api.post<{ data: Subtask }>(
					`/api/todos/${todoId}/subtasks`,
					subtask
				);
				// Update the parent todo's subtasks in the store
				update((todos) =>
					todos.map((t) =>
						t.id === todoId ? { ...t, subtasks: [...(t.subtasks || []), response.data] } : t
					)
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to add subtask:', error);
				throw error;
			}
		},
		completeSubtask: async (todoId: number, subtaskId: number) => {
			try {
				await api.post(`/api/todos/${subtaskId}/complete`, {});
				// Update the subtask status in the store
				update((todos) =>
					todos.map((t) =>
						t.id === todoId
							? {
									...t,
									subtasks: (t.subtasks || []).map((s) =>
										s.id === subtaskId ? { ...s, status: 'completed' as const } : s
									)
								}
							: t
					)
				);
			} catch (error) {
				logger.error('Failed to complete subtask:', error);
				throw error;
			}
		},
		removeSubtask: async (todoId: number, subtaskId: number) => {
			try {
				await api.delete(`/api/todos/${subtaskId}`);
				// Remove the subtask from the store
				update((todos) =>
					todos.map((t) =>
						t.id === todoId
							? { ...t, subtasks: (t.subtasks || []).filter((s) => s.id !== subtaskId) }
							: t
					)
				);
			} catch (error) {
				logger.error('Failed to remove subtask:', error);
				throw error;
			}
		},
		loadSubtasks: async (todoId: number): Promise<Subtask[]> => {
			try {
				const response = await api.get<{ data: Subtask[] }>(`/api/todos/${todoId}/subtasks`);
				// Update the todo's subtasks in the store
				update((todos) =>
					todos.map((t) => (t.id === todoId ? { ...t, subtasks: response.data } : t))
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to load subtasks:', error);
				throw error;
			}
		},
		// Attachment methods
		loadAttachments: async (todoId: number): Promise<Attachment[]> => {
			try {
				const response = await api.get<{ data: Attachment[] }>(`/api/todos/${todoId}/attachments`);
				// Update the todo's attachments in the store
				update((todos) =>
					todos.map((t) => (t.id === todoId ? { ...t, attachments: response.data } : t))
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to load attachments:', error);
				throw error;
			}
		},
		uploadAttachment: async (todoId: number, file: File): Promise<Attachment> => {
			try {
				const response = await api.uploadFile<{ data: Attachment }>(
					`/api/todos/${todoId}/attachments`,
					file
				);
				// Update the todo's attachments in the store
				update((todos) =>
					todos.map((t) =>
						t.id === todoId ? { ...t, attachments: [...(t.attachments || []), response.data] } : t
					)
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to upload attachment:', error);
				throw error;
			}
		},
		removeAttachment: async (todoId: number, attachmentId: number) => {
			try {
				await api.delete(`/api/todos/${todoId}/attachments/${attachmentId}`);
				// Remove the attachment from the store
				update((todos) =>
					todos.map((t) =>
						t.id === todoId
							? {
									...t,
									attachments: (t.attachments || []).filter((a) => a.id !== attachmentId)
								}
							: t
					)
				);
			} catch (error) {
				logger.error('Failed to remove attachment:', error);
				throw error;
			}
		},
		getAttachmentUrl: (todoId: number, attachmentId: number): string => {
			return `/api/todos/${todoId}/attachments/${attachmentId}`;
		},
		reorder: async (todoIds: number[]) => {
			try {
				await api.post('/api/todos/reorder', { todo_ids: todoIds });
				// Update local positions
				update((todos) => {
					const todoMap = new Map(todos.map((t) => [t.id, t]));
					return todoIds
						.map((id, index) => {
							const todo = todoMap.get(id);
							if (todo) {
								return { ...todo, position: index };
							}
							return null;
						})
						.filter((t): t is Todo => t !== null)
						.concat(todos.filter((t) => !todoIds.includes(t.id)));
				});
			} catch (error) {
				logger.error('Failed to reorder todos:', error);
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
