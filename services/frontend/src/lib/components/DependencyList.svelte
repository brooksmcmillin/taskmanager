<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import { getPriorityColor } from '$lib/utils/priority';
	import type { TaskDependency, Todo } from '$lib/types';

	export let todoId: number;
	export let dependencies: TaskDependency[] = [];
	export let dependents: TaskDependency[] = [];

	let showAddForm = false;
	let availableTasks: Todo[] = [];
	let selectedTaskId: number | null = null;
	let isSubmitting = false;
	let isLoadingTasks = false;
	let searchQuery = '';

	const dispatch = createEventDispatcher();

	async function loadAvailableTasks() {
		isLoadingTasks = true;
		try {
			// Load all tasks for the user
			await todos.load({ include_subtasks: false });
			// Get current store value
			const allTodos = await new Promise<Todo[]>((resolve) => {
				const unsubscribe = todos.subscribe((value) => {
					resolve(value);
					unsubscribe();
				});
			});
			// Filter out the current task, subtasks, and already-added dependencies
			const dependencyIds = new Set(dependencies.map((d) => d.id));
			availableTasks = allTodos.filter(
				(t) =>
					t.id !== todoId &&
					!t.parent_id && // Exclude subtasks
					!dependencyIds.has(t.id) &&
					t.status !== 'completed' &&
					t.status !== 'cancelled'
			);
		} catch (error) {
			console.error('Failed to load tasks:', error);
		} finally {
			isLoadingTasks = false;
		}
	}

	function openAddForm() {
		showAddForm = true;
		loadAvailableTasks();
	}

	async function handleAddDependency() {
		if (!selectedTaskId || isSubmitting) return;

		isSubmitting = true;
		try {
			await todos.addDependency(todoId, selectedTaskId);
			selectedTaskId = null;
			showAddForm = false;
			searchQuery = '';
			dispatch('dependencyAdded');
		} catch (error: unknown) {
			console.error('Failed to add dependency:', error);
			// Show error message for circular dependency
			if (error && typeof error === 'object' && 'message' in error) {
				const errorMessage = (error as { message: string }).message;
				if (errorMessage.includes('circular')) {
					alert('Cannot add this dependency: it would create a circular dependency chain.');
				}
			}
		} finally {
			isSubmitting = false;
		}
	}

	async function handleRemoveDependency(dependencyId: number) {
		if (!confirm('Remove this dependency?')) return;
		try {
			await todos.removeDependency(todoId, dependencyId);
			dispatch('dependencyRemoved', dependencyId);
		} catch (error) {
			console.error('Failed to remove dependency:', error);
		}
	}

	function getStatusColor(status: string): string {
		switch (status) {
			case 'completed':
				return '#10b981';
			case 'in_progress':
				return '#3b82f6';
			case 'cancelled':
				return '#6b7280';
			default:
				return '#f59e0b';
		}
	}

	$: filteredTasks = searchQuery
		? availableTasks.filter((t) => t.title.toLowerCase().includes(searchQuery.toLowerCase()))
		: availableTasks;

	$: blockedByIncomplete = dependencies.filter((d) => d.status !== 'completed');
</script>

<div class="dependency-list">
	<!-- Dependencies (tasks this task depends on) -->
	<div class="dependency-section">
		<div class="dependency-header">
			<h4 class="dependency-title">
				Depends On
				{#if dependencies.length > 0}
					<span class="dependency-count">({dependencies.length})</span>
				{/if}
			</h4>
			{#if !showAddForm}
				<button class="add-dependency-btn" on:click={openAddForm} title="Add dependency">
					+
				</button>
			{/if}
		</div>

		{#if blockedByIncomplete.length > 0}
			<div class="blocked-notice">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
					<path
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<span
					>Blocked by {blockedByIncomplete.length} incomplete task{blockedByIncomplete.length > 1
						? 's'
						: ''}</span
				>
			</div>
		{/if}

		{#if showAddForm}
			<div class="add-dependency-form">
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search tasks..."
					class="search-input"
				/>
				{#if isLoadingTasks}
					<p class="loading-text">Loading tasks...</p>
				{:else if filteredTasks.length === 0}
					<p class="no-tasks-text">No available tasks to add as dependency</p>
				{:else}
					<ul class="task-select-list">
						{#each filteredTasks.slice(0, 10) as task (task.id)}
							<li>
								<button
									class="task-select-item"
									class:selected={selectedTaskId === task.id}
									on:click={() => (selectedTaskId = task.id)}
								>
									<span
										class="priority-dot"
										style="background-color: {getPriorityColor(task.priority)}"
									></span>
									<span class="task-title">{task.title}</span>
									{#if task.project_name}
										<span class="task-project">{task.project_name}</span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
					{#if filteredTasks.length > 10}
						<p class="more-tasks-text">
							And {filteredTasks.length - 10} more... refine your search
						</p>
					{/if}
				{/if}
				<div class="form-actions">
					<button
						class="btn btn-sm btn-primary"
						on:click={handleAddDependency}
						disabled={!selectedTaskId || isSubmitting}
					>
						{isSubmitting ? 'Adding...' : 'Add Dependency'}
					</button>
					<button
						class="btn btn-sm btn-secondary"
						on:click={() => {
							showAddForm = false;
							selectedTaskId = null;
							searchQuery = '';
						}}
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}

		<ul class="dependency-items">
			{#each dependencies as dep (dep.id)}
				<li class="dependency-item" class:completed={dep.status === 'completed'}>
					<span
						class="status-indicator"
						style="background-color: {getStatusColor(dep.status)}"
						title={dep.status.replace('_', ' ')}
					></span>
					<div class="dependency-content">
						<span class="dependency-text">{dep.title}</span>
						<div class="dependency-meta">
							<span
								class="priority-dot"
								style="background-color: {getPriorityColor(dep.priority)}"
								title="{dep.priority} priority"
							></span>
							{#if dep.project_name}
								<span class="project-badge">{dep.project_name}</span>
							{/if}
						</div>
					</div>
					<button
						class="delete-btn"
						on:click={() => handleRemoveDependency(dep.id)}
						title="Remove dependency"
					>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</li>
			{/each}
		</ul>

		{#if dependencies.length === 0 && !showAddForm}
			<p class="no-dependencies">No dependencies. Click + to add one.</p>
		{/if}
	</div>

	<!-- Dependents (tasks that depend on this task) -->
	{#if dependents.length > 0}
		<div class="dependency-section dependents-section">
			<div class="dependency-header">
				<h4 class="dependency-title">
					Blocking
					<span class="dependency-count">({dependents.length})</span>
				</h4>
			</div>

			<ul class="dependency-items">
				{#each dependents as dep (dep.id)}
					<li class="dependency-item dependent-item">
						<span
							class="status-indicator"
							style="background-color: {getStatusColor(dep.status)}"
							title={dep.status.replace('_', ' ')}
						></span>
						<div class="dependency-content">
							<span class="dependency-text">{dep.title}</span>
							<div class="dependency-meta">
								<span
									class="priority-dot"
									style="background-color: {getPriorityColor(dep.priority)}"
									title="{dep.priority} priority"
								></span>
								{#if dep.project_name}
									<span class="project-badge">{dep.project_name}</span>
								{/if}
							</div>
						</div>
					</li>
				{/each}
			</ul>

			<p class="dependents-info">These tasks are waiting for this task to be completed.</p>
		</div>
	{/if}
</div>

<style>
	.dependency-list {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--border-color);
	}

	.dependency-section {
		margin-bottom: 1.5rem;
	}

	.dependents-section {
		padding-top: 1rem;
		border-top: 1px solid var(--border-color);
	}

	.dependency-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.dependency-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-secondary);
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.dependency-count {
		font-weight: 400;
		color: var(--text-muted);
		margin-left: 0.5rem;
	}

	.add-dependency-btn {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px dashed var(--gray-400);
		background: transparent;
		color: var(--text-muted);
		font-size: 1.25rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all var(--transition-base);
	}

	.add-dependency-btn:hover {
		border-color: var(--primary-500);
		color: var(--primary-500);
		background-color: var(--primary-50);
	}

	.blocked-notice {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background-color: var(--warning-50, #fffbeb);
		border: 1px solid var(--warning-200, #fde68a);
		border-radius: 0.375rem;
		margin-bottom: 0.75rem;
		font-size: 0.8125rem;
		color: var(--warning-700, #b45309);
	}

	.blocked-notice svg {
		width: 1rem;
		height: 1rem;
		flex-shrink: 0;
	}

	.add-dependency-form {
		background-color: var(--bg-page);
		border-radius: 0.5rem;
		padding: 0.75rem;
		margin-bottom: 1rem;
	}

	.search-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--gray-300);
		border-radius: 0.375rem;
		font-size: 0.875rem;
		background-color: var(--bg-input);
		color: var(--text-primary);
		margin-bottom: 0.5rem;
	}

	.search-input:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
	}

	.loading-text,
	.no-tasks-text,
	.more-tasks-text {
		font-size: 0.8125rem;
		color: var(--text-muted);
		padding: 0.5rem 0;
		margin: 0;
	}

	.task-select-list {
		list-style: none;
		padding: 0;
		margin: 0 0 0.5rem 0;
		max-height: 200px;
		overflow-y: auto;
	}

	.task-select-item {
		width: 100%;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem;
		border: 1px solid transparent;
		background: transparent;
		border-radius: 0.375rem;
		cursor: pointer;
		text-align: left;
		transition: all var(--transition-base);
	}

	.task-select-item:hover {
		background-color: var(--bg-hover);
	}

	.task-select-item.selected {
		background-color: var(--primary-50);
		border-color: var(--primary-500);
	}

	.task-title {
		flex: 1;
		font-size: 0.875rem;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.task-project {
		font-size: 0.75rem;
		color: var(--text-muted);
		padding: 0.125rem 0.375rem;
		background-color: var(--bg-hover);
		border-radius: 0.25rem;
	}

	.form-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		margin-top: 0.5rem;
	}

	.btn {
		padding: 0.375rem 0.75rem;
		border-radius: 0.375rem;
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: all var(--transition-base);
	}

	.btn-sm {
		padding: 0.25rem 0.5rem;
	}

	.btn-primary {
		background-color: var(--primary-500);
		color: white;
	}

	.btn-primary:hover:not(:disabled) {
		background-color: var(--primary-600);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-secondary {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.btn-secondary:hover {
		background-color: var(--bg-active);
	}

	.dependency-items {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.dependency-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border-light);
	}

	.dependency-item:last-child {
		border-bottom: none;
	}

	.dependency-item.completed .dependency-text {
		text-decoration: line-through;
		color: var(--text-muted);
	}

	.status-indicator {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.dependency-content {
		flex: 1;
		min-width: 0;
	}

	.dependency-text {
		font-size: 0.875rem;
		color: var(--text-primary);
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.dependency-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.25rem;
	}

	.priority-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.project-badge {
		font-size: 0.6875rem;
		color: var(--text-muted);
		padding: 0.125rem 0.375rem;
		background-color: var(--bg-hover);
		border-radius: 0.25rem;
	}

	.delete-btn {
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.25rem;
		opacity: 0;
		transition: all var(--transition-base);
	}

	.dependency-item:hover .delete-btn {
		opacity: 1;
	}

	.delete-btn:hover {
		color: var(--error-500);
		background-color: var(--error-50);
	}

	.delete-btn svg {
		width: 1rem;
		height: 1rem;
	}

	.no-dependencies {
		font-size: 0.875rem;
		color: var(--text-muted);
		text-align: center;
		padding: 1rem 0;
		margin: 0;
	}

	.dependents-info {
		font-size: 0.75rem;
		color: var(--text-muted);
		font-style: italic;
		margin: 0.5rem 0 0 0;
	}
</style>
