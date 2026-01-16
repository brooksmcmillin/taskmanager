<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import { toasts } from '$lib/stores/ui';
	import { formatDateForInput } from '$lib/utils/dates';
	import type { Todo, Project } from '$lib/types';

	export let editingTodo: Todo | null = null;

	const dispatch = createEventDispatcher();

	let projectList: Project[] = [];
	let formData = {
		project_id: '',
		title: '',
		description: '',
		priority: 'medium',
		due_date: '',
		tags: ''
	};

	$: isEditing = editingTodo !== null;
	$: submitButtonText = isEditing ? 'Update Todo' : 'Add Todo';

	onMount(() => {
		projects.subscribe((p) => {
			projectList = p;
		});
	});

	$: if (editingTodo) {
		formData = {
			project_id: editingTodo.project_id?.toString() || '',
			title: editingTodo.title,
			description: editingTodo.description || '',
			priority: editingTodo.priority,
			due_date: editingTodo.due_date ? formatDateForInput(editingTodo.due_date) : '',
			tags: editingTodo.tags?.join(', ') || ''
		};
	}

	/**
	 * Resets the form to its initial state
	 */
	export function reset() {
		formData = {
			project_id: '',
			title: '',
			description: '',
			priority: 'medium',
			due_date: '',
			tags: ''
		};
		editingTodo = null;
	}

	/**
	 * Handles form submission for creating or updating a todo
	 */
	async function handleSubmit() {
		try {
			const todoData = {
				project_id: formData.project_id ? parseInt(formData.project_id) : undefined,
				title: formData.title,
				description: formData.description || undefined,
				priority: formData.priority,
				due_date: formData.due_date || undefined,
				tags: formData.tags
					? formData.tags.split(',').map((t) => t.trim())
					: undefined,
				context: 'work'
			};

			if (isEditing && editingTodo) {
				await todos.updateTodo(editingTodo.id, todoData);
				toasts.show('Todo updated successfully', 'success');
			} else {
				await todos.add(todoData);
				toasts.show('Todo created successfully', 'success');
			}

			reset();
			dispatch('success');
		} catch (error) {
			toasts.show(
				`Error ${isEditing ? 'updating' : 'creating'} todo: ` + (error as Error).message,
				'error'
			);
		}
	}

	/**
	 * Handles deleting a todo with confirmation
	 */
	async function handleDelete() {
		if (!editingTodo) return;

		const confirmDelete = confirm(
			'Are you sure you want to delete this todo? This action cannot be undone.'
		);

		if (!confirmDelete) return;

		try {
			await todos.remove(editingTodo.id);
			toasts.show('Todo deleted successfully', 'success');
			reset();
			dispatch('success');
		} catch (error) {
			toasts.show('Error deleting todo: ' + (error as Error).message, 'error');
		}
	}

	/**
	 * Marks the current todo as complete
	 */
	async function handleComplete() {
		if (!editingTodo) return;

		try {
			await todos.complete(editingTodo.id);
			toasts.show('Todo marked as complete', 'success');
			reset();
			dispatch('success');
		} catch (error) {
			toasts.show('Error completing todo: ' + (error as Error).message, 'error');
		}
	}
</script>

<div class="todo-form-container">
	<form class="card" on:submit|preventDefault={handleSubmit}>
		<div class="form-grid">
			<div class="form-full-width">
				<label for="title" class="block text-sm font-medium text-gray-700">Title</label>
				<input
					type="text"
					id="title"
					name="title"
					required
					class="form-input mt-1"
					bind:value={formData.title}
				/>
			</div>

			<div>
				<label for="project_id" class="block text-sm font-medium text-gray-700">Project</label>
				<select id="project_id" name="project_id" class="form-select mt-1" bind:value={formData.project_id}>
					<option value="">Select a project...</option>
					{#each projectList as project}
						<option value={project.id.toString()}>{project.name}</option>
					{/each}
				</select>
			</div>

			<div>
				<label for="due_date" class="block text-sm font-medium text-gray-700"
					>Due Date (Optional)</label
				>
				<input
					type="date"
					id="due_date"
					name="due_date"
					class="form-input mt-1"
					bind:value={formData.due_date}
				/>
			</div>

			<div>
				<label for="tags" class="block text-sm font-medium text-gray-700"
					>Tags (comma-separated)</label
				>
				<input
					type="text"
					id="tags"
					name="tags"
					placeholder="backend, urgent, review"
					class="form-input mt-1"
					bind:value={formData.tags}
				/>
			</div>

			<div>
				<label for="priority" class="block text-sm font-medium text-gray-700">Priority</label>
				<select id="priority" name="priority" class="form-select mt-1" bind:value={formData.priority}>
					<option value="low">Low</option>
					<option value="medium">Medium</option>
					<option value="high">High</option>
					<option value="urgent">Urgent</option>
				</select>
			</div>

			<div class="form-full-width">
				<label for="description" class="block text-sm font-medium text-gray-700"
					>Description</label
				>
				<textarea
					id="description"
					name="description"
					rows="3"
					class="form-textarea mt-1"
					bind:value={formData.description}
				></textarea>
			</div>
		</div>

		<div class="form-submit">
			<div class="form-actions">
				<button type="submit" class="btn btn-primary flex-1">{submitButtonText}</button>
				{#if isEditing}
					<button
						type="button"
						class="btn btn-danger btn-delete"
						on:click={handleDelete}
						title="Delete todo"
					>
						🗑️
					</button>
					<button
						type="button"
						class="btn btn-edit-complete"
						on:click={handleComplete}
						title="Mark as complete"
					>
						✓
					</button>
				{/if}
			</div>
		</div>
	</form>
</div>
