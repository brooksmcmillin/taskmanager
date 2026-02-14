import { derived } from 'svelte/store';
import type {
	Todo,
	TodoFilters,
	TodoCreate,
	TodoUpdate,
	Subtask,
	SubtaskCreate,
	Attachment,
	Comment,
	CommentCreate,
	TaskDependency
} from '$lib/types';
import { api } from '$lib/api/client';
import { logger } from '$lib/utils/logger';
import { createCrudStore } from './createCrudStore';

// --- Store update helpers ---

type TodoArrayKey = 'subtasks' | 'attachments' | 'dependencies' | 'comments';

/** Set a field on a specific todo by ID. */
function setTodoField(todos: Todo[], todoId: number, field: TodoArrayKey, value: unknown): Todo[] {
	return todos.map((t) => (t.id === todoId ? { ...t, [field]: value } : t));
}

/** Append an item to a todo's array field. */
function appendToTodoArray<T>(todos: Todo[], todoId: number, field: TodoArrayKey, item: T): Todo[] {
	return todos.map((t) =>
		t.id === todoId ? { ...t, [field]: [...((t[field] as T[] | undefined) || []), item] } : t
	);
}

/** Remove an item by ID from a todo's array field. */
function removeFromTodoArray(
	todos: Todo[],
	todoId: number,
	field: TodoArrayKey,
	itemId: number
): Todo[] {
	return todos.map((t) =>
		t.id === todoId
			? {
					...t,
					[field]: ((t[field] as { id: number }[] | undefined) || []).filter(
						(item) => item.id !== itemId
					)
				}
			: t
	);
}

// --- Store ---

function createTodoStore() {
	const store = createCrudStore<Todo, TodoCreate, TodoUpdate>({
		endpoint: '/api/todos',
		entityName: 'todo',
		reorderKey: 'todo_ids'
	});

	return {
		subscribe: store.subscribe,
		load: async (filters?: TodoFilters & { include_subtasks?: boolean }) => {
			try {
				// Always include subtasks by default
				const mergedFilters = { include_subtasks: true, ...filters };
				// Convert filter values to strings properly
				const params = Object.fromEntries(
					Object.entries(mergedFilters)
						.filter(([, value]) => value !== undefined)
						.map(([key, value]) => [key, String(value)])
				) as Record<string, string>;

				const response = await api.get<{ data: Todo[]; meta: { count: number } }>('/api/todos', {
					params
				});
				store.set(response.data || []);
			} catch (error) {
				logger.error('Failed to load todos:', error);
				throw error;
			}
		},
		add: store.add,
		updateTodo: store.updateItem,
		remove: store.remove,
		getById: store.getById,
		reorder: store.reorder,
		complete: async (id: number) => {
			try {
				await api.post(`/api/todos/${id}/complete`, {});
				store.update((todos) =>
					todos.map((t) => (t.id === id ? { ...t, status: 'completed' as const } : t))
				);
			} catch (error) {
				logger.error('Failed to complete todo:', error);
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
				store.update((todos) => appendToTodoArray(todos, todoId, 'subtasks', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to add subtask:', error);
				throw error;
			}
		},
		completeSubtask: async (todoId: number, subtaskId: number) => {
			try {
				await api.post(`/api/todos/${subtaskId}/complete`, {});
				store.update((todos) =>
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
				store.update((todos) => removeFromTodoArray(todos, todoId, 'subtasks', subtaskId));
			} catch (error) {
				logger.error('Failed to remove subtask:', error);
				throw error;
			}
		},
		loadSubtasks: async (todoId: number): Promise<Subtask[]> => {
			try {
				const response = await api.get<{ data: Subtask[] }>(`/api/todos/${todoId}/subtasks`);
				store.update((todos) => setTodoField(todos, todoId, 'subtasks', response.data));
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
				store.update((todos) => setTodoField(todos, todoId, 'attachments', response.data));
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
				store.update((todos) => appendToTodoArray(todos, todoId, 'attachments', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to upload attachment:', error);
				throw error;
			}
		},
		removeAttachment: async (todoId: number, attachmentId: number) => {
			try {
				await api.delete(`/api/todos/${todoId}/attachments/${attachmentId}`);
				store.update((todos) => removeFromTodoArray(todos, todoId, 'attachments', attachmentId));
			} catch (error) {
				logger.error('Failed to remove attachment:', error);
				throw error;
			}
		},
		getAttachmentUrl: (todoId: number, attachmentId: number): string => {
			return `/api/todos/${todoId}/attachments/${attachmentId}`;
		},
		// Dependency methods
		loadDependencies: async (todoId: number): Promise<TaskDependency[]> => {
			try {
				const response = await api.get<{ data: TaskDependency[] }>(
					`/api/todos/${todoId}/dependencies`
				);
				store.update((todos) => setTodoField(todos, todoId, 'dependencies', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to load dependencies:', error);
				throw error;
			}
		},
		addDependency: async (todoId: number, dependencyId: number): Promise<TaskDependency> => {
			try {
				const response = await api.post<{ data: TaskDependency }>(
					`/api/todos/${todoId}/dependencies`,
					{ dependency_id: dependencyId }
				);
				store.update((todos) => appendToTodoArray(todos, todoId, 'dependencies', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to add dependency:', error);
				throw error;
			}
		},
		removeDependency: async (todoId: number, dependencyId: number): Promise<void> => {
			try {
				await api.delete(`/api/todos/${todoId}/dependencies/${dependencyId}`);
				store.update((todos) => removeFromTodoArray(todos, todoId, 'dependencies', dependencyId));
			} catch (error) {
				logger.error('Failed to remove dependency:', error);
				throw error;
			}
		},
		// Comment methods
		loadComments: async (todoId: number): Promise<Comment[]> => {
			try {
				const response = await api.get<{ data: Comment[] }>(`/api/todos/${todoId}/comments`);
				store.update((todos) => setTodoField(todos, todoId, 'comments', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to load comments:', error);
				throw error;
			}
		},
		addComment: async (todoId: number, comment: CommentCreate): Promise<Comment> => {
			try {
				const response = await api.post<{ data: Comment }>(
					`/api/todos/${todoId}/comments`,
					comment
				);
				store.update((todos) => appendToTodoArray(todos, todoId, 'comments', response.data));
				return response.data;
			} catch (error) {
				logger.error('Failed to add comment:', error);
				throw error;
			}
		},
		updateComment: async (todoId: number, commentId: number, content: string): Promise<Comment> => {
			try {
				const response = await api.put<{ data: Comment }>(
					`/api/todos/${todoId}/comments/${commentId}`,
					{ content }
				);
				store.update((todos) =>
					todos.map((t) =>
						t.id === todoId
							? {
									...t,
									comments: ((t.comments as Comment[] | undefined) || []).map((c) =>
										c.id === commentId ? response.data : c
									)
								}
							: t
					)
				);
				return response.data;
			} catch (error) {
				logger.error('Failed to update comment:', error);
				throw error;
			}
		},
		removeComment: async (todoId: number, commentId: number): Promise<void> => {
			try {
				await api.delete(`/api/todos/${todoId}/comments/${commentId}`);
				store.update((todos) => removeFromTodoArray(todos, todoId, 'comments', commentId));
			} catch (error) {
				logger.error('Failed to remove comment:', error);
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
