<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { recurringTasks } from '$lib/stores/recurringTasks';
	import { projects } from '$lib/stores/projects';
	import { toasts } from '$lib/stores/ui';
	import { formatDateForInput } from '$lib/utils/dates';
	import type { RecurringTask, Project, Frequency } from '$lib/types';

	export let editingTask: RecurringTask | null = null;

	const dispatch = createEventDispatcher();

	let projectList: Project[] = [];
	let formData = {
		project_id: '',
		title: '',
		description: '',
		priority: 'medium',
		start_date: '',
		end_date: '',
		tags: '',
		frequency: 'daily' as Frequency,
		interval_value: 1,
		weekdays: [] as number[],
		day_of_month: 1,
		skip_missed: true
	};

	const weekdayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	$: isEditing = editingTask !== null;
	$: submitButtonText = isEditing ? 'Update Recurring Task' : 'Create Recurring Task';

	onMount(() => {
		projects.subscribe((p) => {
			projectList = p;
		});
	});

	$: if (editingTask) {
		formData = {
			project_id: editingTask.project_id?.toString() || '',
			title: editingTask.title,
			description: editingTask.description || '',
			priority: editingTask.priority,
			start_date: editingTask.start_date ? formatDateForInput(editingTask.start_date) : '',
			end_date: editingTask.end_date ? formatDateForInput(editingTask.end_date) : '',
			tags: editingTask.tags?.join(', ') || '',
			frequency: editingTask.frequency,
			interval_value: editingTask.interval_value,
			weekdays: editingTask.weekdays || [],
			day_of_month: editingTask.day_of_month || 1,
			skip_missed: editingTask.skip_missed
		};
	}

	function toggleWeekday(day: number) {
		if (formData.weekdays.includes(day)) {
			formData.weekdays = formData.weekdays.filter((d) => d !== day);
		} else {
			formData.weekdays = [...formData.weekdays, day];
		}
	}

	export function reset() {
		formData = {
			project_id: '',
			title: '',
			description: '',
			priority: 'medium',
			start_date: '',
			end_date: '',
			tags: '',
			frequency: 'daily' as Frequency,
			interval_value: 1,
			weekdays: [],
			day_of_month: 1,
			skip_missed: true
		};
		editingTask = null;
	}

	async function handleSubmit() {
		try {
			const taskData = {
				project_id: formData.project_id ? parseInt(formData.project_id) : undefined,
				title: formData.title,
				description: formData.description || undefined,
				priority: formData.priority,
				start_date: formData.start_date || new Date().toISOString().split('T')[0],
				end_date: formData.end_date || undefined,
				tags: formData.tags ? formData.tags.split(',').map((t) => t.trim()) : undefined,
				context: 'work',
				frequency: formData.frequency,
				interval_value: formData.interval_value,
				weekdays:
					formData.frequency === 'weekly' && formData.weekdays.length > 0
						? formData.weekdays
						: undefined,
				day_of_month: formData.frequency === 'monthly' ? formData.day_of_month : undefined,
				skip_missed: formData.skip_missed
			};

			if (isEditing && editingTask) {
				await recurringTasks.updateTask(editingTask.id, taskData);
				toasts.show('Recurring task updated successfully', 'success');
			} else {
				await recurringTasks.add(taskData);
				toasts.show('Recurring task created successfully', 'success');
			}

			reset();
			dispatch('success');
		} catch (error) {
			toasts.show(
				`Error ${isEditing ? 'updating' : 'creating'} recurring task: ` + (error as Error).message,
				'error'
			);
		}
	}

	async function handleDelete() {
		if (!editingTask) return;

		const confirmDelete = confirm(
			'Are you sure you want to delete this recurring task? This action cannot be undone.'
		);

		if (!confirmDelete) return;

		try {
			await recurringTasks.remove(editingTask.id);
			toasts.show('Recurring task deleted successfully', 'success');
			reset();
			dispatch('success');
		} catch (error) {
			toasts.show('Error deleting recurring task: ' + (error as Error).message, 'error');
		}
	}
</script>

<div class="recurring-task-form-container">
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
				<select
					id="project_id"
					name="project_id"
					class="form-select mt-1"
					bind:value={formData.project_id}
				>
					<option value="">Select a project...</option>
					{#each projectList as project}
						<option value={project.id.toString()}>{project.name}</option>
					{/each}
				</select>
			</div>

			<div>
				<label for="priority" class="block text-sm font-medium text-gray-700">Priority</label>
				<select
					id="priority"
					name="priority"
					class="form-select mt-1"
					bind:value={formData.priority}
				>
					<option value="low">Low</option>
					<option value="medium">Medium</option>
					<option value="high">High</option>
					<option value="urgent">Urgent</option>
				</select>
			</div>

			<div>
				<label for="frequency" class="block text-sm font-medium text-gray-700">Frequency</label>
				<select id="frequency" class="form-select mt-1" bind:value={formData.frequency}>
					<option value="daily">Daily</option>
					<option value="weekly">Weekly</option>
					<option value="monthly">Monthly</option>
					<option value="yearly">Yearly</option>
				</select>
			</div>

			<div>
				<label for="interval" class="block text-sm font-medium text-gray-700">Every</label>
				<div class="interval-input">
					<input
						type="number"
						id="interval"
						min="1"
						max="365"
						class="form-input mt-1"
						bind:value={formData.interval_value}
					/>
					<span class="interval-label">
						{formData.frequency === 'daily'
							? 'day(s)'
							: formData.frequency === 'weekly'
								? 'week(s)'
								: formData.frequency === 'monthly'
									? 'month(s)'
									: 'year(s)'}
					</span>
				</div>
			</div>

			{#if formData.frequency === 'weekly'}
				<div class="form-full-width">
					<label class="block text-sm font-medium text-gray-700 mb-2">On days</label>
					<div class="weekday-picker">
						{#each weekdayNames as day, index}
							<button
								type="button"
								class="weekday-btn"
								class:selected={formData.weekdays.includes(index)}
								on:click={() => toggleWeekday(index)}
							>
								{day}
							</button>
						{/each}
					</div>
				</div>
			{/if}

			{#if formData.frequency === 'monthly'}
				<div>
					<label for="day_of_month" class="block text-sm font-medium text-gray-700"
						>Day of month</label
					>
					<input
						type="number"
						id="day_of_month"
						min="1"
						max="31"
						class="form-input mt-1"
						bind:value={formData.day_of_month}
					/>
				</div>
			{/if}

			<div>
				<label for="start_date" class="block text-sm font-medium text-gray-700">Start Date</label>
				<input
					type="date"
					id="start_date"
					name="start_date"
					class="form-input mt-1"
					bind:value={formData.start_date}
				/>
			</div>

			<div>
				<label for="end_date" class="block text-sm font-medium text-gray-700"
					>End Date (Optional)</label
				>
				<input
					type="date"
					id="end_date"
					name="end_date"
					class="form-input mt-1"
					bind:value={formData.end_date}
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

			<div class="skip-missed-toggle">
				<label class="toggle-label">
					<input type="checkbox" bind:checked={formData.skip_missed} class="toggle-checkbox" />
					<span class="toggle-text">Skip missed occurrences</span>
				</label>
				<p class="text-xs text-gray-500 mt-1">
					If enabled, only the next occurrence will be created
				</p>
			</div>

			<div class="form-full-width">
				<label for="description" class="block text-sm font-medium text-gray-700">Description</label>
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
						title="Delete recurring task"
					>
						Delete
					</button>
				{/if}
			</div>
		</div>
	</form>
</div>

<style>
	.interval-input {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.interval-input input {
		width: 5rem;
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
		grid-column: span 2;
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

	/* Dark mode support */
	:global(.dark) .toggle-text {
		color: #d1d5db;
	}

	:global(.dark) .weekday-btn {
		background-color: #374151;
		border-color: #4b5563;
		color: #d1d5db;
	}

	:global(.dark) .weekday-btn:hover {
		border-color: #60a5fa;
		color: #60a5fa;
	}

	:global(.dark) .weekday-btn.selected {
		background-color: #2563eb;
		border-color: #2563eb;
		color: white;
	}

	:global(.dark) .interval-label {
		color: #9ca3af;
	}
</style>
