<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import { recurringTasks } from '$lib/stores/recurringTasks';
	import { toasts } from '$lib/stores/ui';
	import { formatDateForInput } from '$lib/utils/dates';
	import type { Todo, Project, Frequency } from '$lib/types';

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

	// Repeat/recurring task options
	let enableRepeat = false;
	let repeatData = {
		frequency: 'daily' as Frequency,
		interval_value: 1,
		weekdays: [] as number[],
		day_of_month: 1,
		end_date: '',
		skip_missed: true
	};

	const weekdayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	function toggleWeekday(day: number) {
		if (repeatData.weekdays.includes(day)) {
			repeatData.weekdays = repeatData.weekdays.filter((d) => d !== day);
		} else {
			repeatData.weekdays = [...repeatData.weekdays, day];
		}
	}

	$: isEditing = editingTodo !== null;
	$: submitButtonText = isEditing
		? 'Update Todo'
		: enableRepeat
			? 'Create Recurring Task'
			: 'Add Todo';

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
		enableRepeat = false;
		repeatData = {
			frequency: 'daily' as Frequency,
			interval_value: 1,
			weekdays: [],
			day_of_month: 1,
			end_date: '',
			skip_missed: true
		};
		editingTodo = null;
	}

	/**
	 * Handles form submission for creating or updating a todo
	 */
	async function handleSubmit() {
		// Validate weekly tasks require at least one weekday
		if (enableRepeat && repeatData.frequency === 'weekly' && repeatData.weekdays.length === 0) {
			toasts.show('Please select at least one day for weekly tasks', 'error');
			return;
		}

		try {
			const baseData = {
				project_id: formData.project_id ? parseInt(formData.project_id) : undefined,
				title: formData.title,
				description: formData.description || undefined,
				priority: formData.priority,
				tags: formData.tags ? formData.tags.split(',').map((t) => t.trim()) : undefined,
				context: 'work'
			};

			if (isEditing && editingTodo) {
				// Can't convert existing todo to recurring, just update normally
				const todoData = {
					...baseData,
					due_date: formData.due_date || undefined
				};
				await todos.updateTodo(editingTodo.id, todoData);
				toasts.show('Todo updated successfully', 'success');
			} else if (enableRepeat) {
				// Create a recurring task instead
				const recurringData = {
					...baseData,
					frequency: repeatData.frequency,
					interval_value: repeatData.interval_value,
					start_date: formData.due_date || new Date().toISOString().split('T')[0],
					weekdays:
						repeatData.frequency === 'weekly' && repeatData.weekdays.length > 0
							? repeatData.weekdays
							: undefined,
					day_of_month: repeatData.frequency === 'monthly' ? repeatData.day_of_month : undefined,
					end_date: repeatData.end_date || undefined,
					skip_missed: repeatData.skip_missed
				};
				await recurringTasks.add(recurringData);
				toasts.show('Recurring task created successfully', 'success');
			} else {
				// Create regular todo
				const todoData = {
					...baseData,
					due_date: formData.due_date || undefined
				};
				await todos.add(todoData);
				toasts.show('Todo created successfully', 'success');
			}

			reset();
			dispatch('success');
		} catch (error) {
			toasts.show(
				`Error ${isEditing ? 'updating' : 'creating'} ${enableRepeat ? 'recurring task' : 'todo'}: ` +
					(error as Error).message,
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
	<form on:submit|preventDefault={handleSubmit}>
		<!-- Title -->
		<div class="form-section">
			<label for="title" class="form-label">Title</label>
			<input
				type="text"
				id="title"
				name="title"
				required
				class="form-input"
				bind:value={formData.title}
			/>
		</div>

		<!-- Description -->
		<div class="form-section">
			<label for="description" class="form-label">Description</label>
			<textarea
				id="description"
				name="description"
				rows="3"
				class="form-textarea"
				bind:value={formData.description}
			></textarea>
		</div>

		<!-- Project -->
		<div class="form-section">
			<label for="project_id" class="form-label">Project</label>
			<select
				id="project_id"
				name="project_id"
				class="form-select"
				bind:value={formData.project_id}
			>
				<option value="">Select a project...</option>
				{#each projectList as project}
					<option value={project.id.toString()}>{project.name}</option>
				{/each}
			</select>
		</div>

		<!-- Priority -->
		<div class="form-section">
			<label for="priority" class="form-label">Priority</label>
			<select id="priority" name="priority" class="form-select" bind:value={formData.priority}>
				<option value="low">Low</option>
				<option value="medium">Medium</option>
				<option value="high">High</option>
				<option value="urgent">Urgent</option>
			</select>
		</div>

		<!-- Due Date -->
		<div class="form-section">
			<label for="due_date" class="form-label"
				>{enableRepeat ? 'Start Date' : 'Due Date'} (Optional)</label
			>
			<input
				type="date"
				id="due_date"
				name="due_date"
				class="form-input"
				bind:value={formData.due_date}
			/>
		</div>

		<!-- Tags -->
		<div class="form-section">
			<label for="tags" class="form-label">Tags (comma-separated)</label>
			<input
				type="text"
				id="tags"
				name="tags"
				placeholder="backend, urgent, review"
				class="form-input"
				bind:value={formData.tags}
			/>
		</div>

		<!-- Repeat Options -->
		{#if !isEditing}
			<div class="form-section repeat-section">
				<div class="repeat-toggle">
					<label class="toggle-label">
						<input type="checkbox" bind:checked={enableRepeat} class="toggle-checkbox" />
						<span class="toggle-text">Repeat this task</span>
					</label>
				</div>

				{#if enableRepeat}
					<div class="repeat-options">
						<div class="form-section">
							<label for="frequency" class="form-label">Frequency</label>
							<select id="frequency" class="form-select" bind:value={repeatData.frequency}>
								<option value="daily">Daily</option>
								<option value="weekly">Weekly</option>
								<option value="monthly">Monthly</option>
								<option value="yearly">Yearly</option>
							</select>
						</div>

						<div class="form-section">
							<label for="interval" class="form-label">Every</label>
							<div class="interval-input">
								<input
									type="number"
									id="interval"
									min="1"
									max="365"
									class="form-input"
									bind:value={repeatData.interval_value}
								/>
								<span class="interval-label">
									{repeatData.frequency === 'daily'
										? 'day(s)'
										: repeatData.frequency === 'weekly'
											? 'week(s)'
											: repeatData.frequency === 'monthly'
												? 'month(s)'
												: 'year(s)'}
								</span>
							</div>
						</div>

						{#if repeatData.frequency === 'weekly'}
							<div class="form-section">
								<label class="form-label">On days</label>
								<div class="weekday-picker">
									{#each weekdayNames as day, index}
										<button
											type="button"
											class="weekday-btn"
											class:selected={repeatData.weekdays.includes(index)}
											on:click={() => toggleWeekday(index)}
										>
											{day}
										</button>
									{/each}
								</div>
							</div>
						{/if}

						{#if repeatData.frequency === 'monthly'}
							<div class="form-section">
								<label for="day_of_month" class="form-label">Day of month</label>
								<input
									type="number"
									id="day_of_month"
									min="1"
									max="31"
									class="form-input"
									bind:value={repeatData.day_of_month}
								/>
							</div>
						{/if}

						<div class="form-section">
							<label for="end_date" class="form-label">End Date (Optional)</label>
							<input
								type="date"
								id="end_date"
								class="form-input"
								bind:value={repeatData.end_date}
							/>
						</div>

						<div class="form-section skip-missed-toggle">
							<label class="toggle-label">
								<input
									type="checkbox"
									bind:checked={repeatData.skip_missed}
									class="toggle-checkbox"
								/>
								<span class="toggle-text">Skip missed occurrences</span>
							</label>
							<p class="text-xs text-gray-500 mt-1">
								If enabled, only the next occurrence will be created
							</p>
						</div>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Actions -->
		<div class="form-actions">
			<button type="submit" class="btn btn-primary">{submitButtonText}</button>
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
	</form>
</div>

<style>
	.todo-form-container {
		/* Remove any default container styling */
	}

	.form-section {
		margin-bottom: 1.5rem;
	}

	.form-label {
		display: block;
		font-size: 0.6875rem;
		font-weight: 700;
		color: #374151;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: 0.5rem;
	}

	.form-input,
	.form-textarea,
	.form-select {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: 1px solid #e5e7eb;
		border-radius: 0.375rem;
		font-size: 0.875rem;
		color: #374151;
		background-color: white;
		transition: border-color 0.15s ease-in-out;
	}

	.form-input:focus,
	.form-textarea:focus,
	.form-select:focus {
		outline: none;
		border-color: #2563eb;
		box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
	}

	.form-textarea {
		resize: vertical;
		min-height: 80px;
	}

	.repeat-section {
		padding-top: 1.5rem;
		border-top: 1px solid #e5e7eb;
	}

	.repeat-toggle {
		margin-bottom: 1rem;
	}

	.toggle-label {
		display: flex;
		align-items: center;
		cursor: pointer;
	}

	.toggle-checkbox {
		width: 1.25rem;
		height: 1.25rem;
		margin-right: 0.5rem;
		accent-color: #2563eb;
	}

	.toggle-text {
		font-size: 0.875rem;
		font-weight: 500;
		color: #374151;
	}

	.repeat-options {
		padding-top: 1rem;
	}

	.interval-input {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.interval-input input {
		flex: 0 0 5rem;
	}

	.interval-label {
		font-size: 0.875rem;
		color: #6b7280;
	}

	.weekday-picker {
		display: flex;
		gap: 0.25rem;
		flex-wrap: wrap;
	}

	.weekday-btn {
		padding: 0.5rem 0.75rem;
		border: 1px solid #d1d5db;
		border-radius: 0.375rem;
		background-color: white;
		font-size: 0.75rem;
		font-weight: 500;
		color: #374151;
		cursor: pointer;
		transition: all 0.15s ease-in-out;
	}

	.weekday-btn:hover {
		border-color: #2563eb;
		color: #2563eb;
	}

	.weekday-btn.selected {
		background-color: #2563eb;
		border-color: #2563eb;
		color: white;
	}

	.skip-missed-toggle {
		margin-top: 1rem;
	}

	.form-actions {
		display: flex;
		gap: 0.75rem;
		margin-top: 2rem;
		padding-top: 1.5rem;
		border-top: 1px solid #e5e7eb;
	}

	.form-actions .btn-primary {
		flex: 1;
		margin-left: 0;
	}

	.form-actions .btn-delete,
	.form-actions .btn-edit-complete {
		margin-left: 0;
	}
</style>
