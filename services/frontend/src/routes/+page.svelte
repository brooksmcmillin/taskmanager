<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { todos, pendingTodos, todosByProject } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import TaskDetailPanel from '$lib/components/TaskDetailPanel.svelte';
	import DragDropCalendar from '$lib/components/DragDropCalendar.svelte';
	import ProjectFilter from '$lib/components/ProjectFilter.svelte';
	import DueDateFilter from '$lib/components/DueDateFilter.svelte';
	import { computeDueDateFilters } from '$lib/utils/dueDateFilter';
	import type { DueDateOption, DueDateFilterValue } from '$lib/utils/dueDateFilter';
	import { getPriorityColor } from '$lib/utils/priority';
	import { contrastText } from '$lib/utils/colors';
	import { formatDateDisplay } from '$lib/utils/dates';
	import { logger } from '$lib/utils/logger';
	import type { Todo } from '$lib/types';

	let currentView: 'list' | 'calendar' = 'calendar';
	let minimizedProjects: Record<string, boolean> = {};
	let taskDetailPanel: TaskDetailPanel;
	let initialLoadComplete = false;

	// Extract filters from URL
	$: selectedProjectId = $page.url.searchParams.get('project_id')
		? parseInt($page.url.searchParams.get('project_id')!)
		: null;

	$: selectedDueDate = ($page.url.searchParams.get('due_date') as DueDateOption) || 'all';

	function getProjectId(projectName: string): string {
		return `project-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
	}

	onMount(async () => {
		// Load projects first
		await projects.load();

		// Load todos with filters if present
		await todos.load({
			status: 'pending',
			...(selectedProjectId && { project_id: selectedProjectId }),
			...computeDueDateFilters(selectedDueDate)
		});

		// Load minimized state from localStorage
		const stored = localStorage.getItem('minimized-projects');
		if (stored) {
			try {
				minimizedProjects = JSON.parse(stored);
			} catch (e) {
				minimizedProjects = {};
			}
		}

		// Mark initial load as complete
		initialLoadComplete = true;
	});

	function toggleProject(projectName: string) {
		const projectId = getProjectId(projectName);
		minimizedProjects[projectId] = !minimizedProjects[projectId];
		localStorage.setItem('minimized-projects', JSON.stringify(minimizedProjects));
	}

	function isProjectMinimized(projectName: string): boolean {
		return minimizedProjects[getProjectId(projectName)] || false;
	}

	function handleFilterChange(event: CustomEvent<{ projectId: number | null }>) {
		const { projectId } = event.detail;
		const url = new URL($page.url);

		if (projectId) {
			url.searchParams.set('project_id', String(projectId));
		} else {
			url.searchParams.delete('project_id');
		}

		goto(url, { replaceState: true, keepFocus: true });
	}

	function handleDueDateFilterChange(event: CustomEvent<DueDateFilterValue>) {
		const url = new URL($page.url);

		if (event.detail.option !== 'all') {
			url.searchParams.set('due_date', event.detail.option);
		} else {
			url.searchParams.delete('due_date');
		}

		goto(url, { replaceState: true, keepFocus: true });
	}

	function openTaskDetail(todo: Todo) {
		taskDetailPanel.open(todo);
	}

	function openEditPanel(todo: Todo) {
		taskDetailPanel.openEdit(todo);
	}

	async function handleCompleteTodo(todoId: number) {
		try {
			await todos.complete(todoId);
			// Reload todos after completion with current filters
			await todos.load({
				status: 'pending',
				...(selectedProjectId && { project_id: selectedProjectId }),
				...computeDueDateFilters(selectedDueDate)
			});
		} catch (error) {
			logger.error('Failed to complete todo:', error);
			alert('Failed to complete todo');
		}
	}

	async function handleFormSuccess() {
		await todos.load({
			status: 'pending',
			...(selectedProjectId && { project_id: selectedProjectId }),
			...computeDueDateFilters(selectedDueDate)
		});
	}

	// Reload todos when filters change (only in browser, after initial load)
	// selectedProjectId and selectedDueDate are reactive via URL params, triggering this block
	$: if (browser && initialLoadComplete) {
		// Reference both reactive values to establish dependencies
		const _projectId = selectedProjectId;
		const _dueDate = selectedDueDate;
		todos.load({
			status: 'pending',
			...(_projectId ? { project_id: _projectId } : {}),
			...computeDueDateFilters(_dueDate)
		});
	}

	// Group todos by project for list view
	$: groupedTodos = $pendingTodos.reduce(
		(acc, todo) => {
			const projectName = todo.project_name || 'No Project';
			if (!acc[projectName]) acc[projectName] = [];
			acc[projectName].push(todo);
			return acc;
		},
		{} as Record<string, Todo[]>
	);

	// Sort project names
	$: sortedProjectNames = Object.keys(groupedTodos).sort();
</script>

<svelte:head>
	<title>Todo Manager</title>
</svelte:head>

<main class="container py-8">
	<!-- View Toggle and Project Filter -->
	<div class="toolbar mb-6">
		<!-- View Toggle (Left) -->
		<div class="toolbar-views">
			<button
				class="btn {currentView === 'list' ? 'btn-primary' : 'btn-secondary'} btn-med"
				on:click={() => (currentView = 'list')}
			>
				List View
			</button>
			<button
				class="btn {currentView === 'calendar' ? 'btn-primary' : 'btn-secondary'} btn-med"
				on:click={() => (currentView = 'calendar')}
			>
				Calendar View
			</button>
		</div>

		<!-- Filters (Right) -->
		<div class="toolbar-filters">
			<DueDateFilter selected={selectedDueDate} on:change={handleDueDateFilterChange} />
			<ProjectFilter {selectedProjectId} on:change={handleFilterChange} />
		</div>
	</div>

	<!-- Task Detail Panel -->
	<TaskDetailPanel
		bind:this={taskDetailPanel}
		on:complete={(e) => handleCompleteTodo(e.detail)}
		on:formSuccess={handleFormSuccess}
	/>

	<!-- Add Todo Button -->
	<button class="add-todo-btn" on:click={() => taskDetailPanel.openCreate()}>
		<span class="plus-icon">+</span>
	</button>

	<!-- List View -->
	{#if currentView === 'list'}
		<div id="list-view">
			<div id="todo-lists" class="grid grid-cols-1 md:grid-cols-2 gap-6">
				{#each sortedProjectNames as projectName}
					{@const projectTodos = groupedTodos[projectName]}
					<div class="card">
						<div class="mb-3">
							<h3 class="font-semibold text-lg text-gray-800">{projectName}</h3>
						</div>
						<div class="space-y-3">
							{#each projectTodos as todo}
								{@const subtasks = todo.subtasks || []}
								{@const pendingSubtasks = subtasks.filter((s) => s.status !== 'completed')}
								{@const completedSubtaskCount = subtasks.length - pendingSubtasks.length}
								<div class="todo-with-subtasks">
									<div
										class="flex items-center justify-between p-4 border rounded border-l-4 hover:shadow-md transition-shadow cursor-pointer"
										style="border-left-color: {todo.project_color || '#6b7280'}"
										on:click={() => openTaskDetail(todo)}
										role="button"
										tabindex="0"
										on:keydown={(e) => e.key === 'Enter' && openTaskDetail(todo)}
									>
										<div class="flex-1">
											<div class="flex items-center gap-2">
												<span
													class="w-2 h-2 rounded-full flex-shrink-0"
													style="background-color: {getPriorityColor(todo.priority)}"
													title="{todo.priority} priority"
												></span>
												<div class="text-base font-medium text-gray-900">{todo.title}</div>
												{#if subtasks.length > 0}
													<span
														class="subtask-badge"
														title="{pendingSubtasks.length} pending of {subtasks.length} subtasks"
													>
														{completedSubtaskCount}/{subtasks.length}
													</span>
												{/if}
											</div>
											<div class="text-xs text-gray-500 mt-1.5 ml-4">
												{todo.priority.charAt(0).toUpperCase() + todo.priority.slice(1)}
												{#if todo.due_date}
													• Due: {formatDateDisplay(todo.due_date)}
												{/if}
											</div>
										</div>
										<div class="flex gap-2 ml-4">
											<button
												on:click|stopPropagation={() => openEditPanel(todo)}
												class="btn btn-secondary btn-sm"
												title="Edit todo"
											>
												✏️
											</button>
											<button
												on:click|stopPropagation={() => handleCompleteTodo(todo.id)}
												class="btn btn-success btn-sm"
												title="Mark as complete"
											>
												✓
											</button>
										</div>
									</div>
									{#each pendingSubtasks as subtask}
										<a
											class="subtask-item-card"
											href="/task/{subtask.id}"
											style="border-left-color: {todo.project_color || '#6b7280'}"
										>
											<div
												class="subtask-item-parent-header"
												style="background-color: {todo.project_color ||
													'#6b7280'}; color: {contrastText(todo.project_color || '#6b7280')}"
											>
												#{todo.id}
												{todo.title}
											</div>
											<div class="subtask-item-content">
												<span
													class="subtask-priority-dot"
													style="background-color: {getPriorityColor(subtask.priority)}"
													title="{subtask.priority} priority"
												></span>
												<span class="subtask-title-text">{subtask.title}</span>
												<span class="subtask-status-pill {subtask.status}">
													{subtask.status.replace('_', ' ')}
												</span>
											</div>
										</a>
									{/each}
								</div>
							{/each}
						</div>
					</div>
				{/each}
			</div>
		</div>
	{/if}

	<!-- Calendar View -->
	{#if currentView === 'calendar'}
		<div id="calendar-view">
			<DragDropCalendar
				filters={{
					...(selectedProjectId ? { project_id: selectedProjectId } : {}),
					...computeDueDateFilters(selectedDueDate)
				}}
				on:editTodo={(e) => openTaskDetail(e.detail)}
			/>
		</div>
	{/if}
</main>

<style>
	.toolbar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 1rem;
	}

	.toolbar-views {
		display: flex;
		gap: 0.5rem;
	}

	.toolbar-filters {
		display: flex;
		gap: 0.75rem;
		align-items: center;
	}

	/* Subtask badge on parent task row */
	.subtask-badge {
		font-size: 0.625rem;
		font-weight: 600;
		background-color: var(--gray-100, #f3f4f6);
		color: var(--text-secondary, #6b7280);
		padding: 0.125rem 0.375rem;
		border-radius: 999px;
		white-space: nowrap;
		line-height: 1;
	}

	/* Subtask item cards in list view */
	.subtask-item-card {
		display: block;
		margin-left: 1.5rem;
		margin-top: 0.25rem;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--border-color, #e5e7eb);
		border-left: 4px solid;
		border-radius: var(--radius-sm, 0.25rem);
		text-decoration: none;
		color: var(--text-primary, #1f2937);
		background-color: var(--bg-primary, #fff);
		transition: box-shadow 0.15s ease;
	}

	.subtask-item-card:hover {
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
	}

	.subtask-item-parent-header {
		font-size: 0.625rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		margin: -0.5rem -0.75rem 0.25rem -0.75rem;
		padding: 0.25rem 0.75rem;
		border-radius: var(--radius-sm, 0.25rem) var(--radius-sm, 0.25rem) 0 0;
	}

	.subtask-item-content {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.8125rem;
	}

	.subtask-priority-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.subtask-title-text {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.subtask-status-pill {
		font-size: 0.625rem;
		font-weight: 500;
		padding: 0.0625rem 0.375rem;
		border-radius: 999px;
		text-transform: capitalize;
		white-space: nowrap;
		flex-shrink: 0;
	}

	.subtask-status-pill.pending {
		background-color: var(--gray-100, #f3f4f6);
		color: var(--text-secondary, #6b7280);
	}

	.subtask-status-pill.in_progress {
		background-color: #dbeafe;
		color: #1d4ed8;
	}

	@media (max-width: 768px) {
		/* $breakpoint-md */
		.toolbar {
			flex-direction: column;
			align-items: stretch;
		}

		.toolbar-views {
			justify-content: stretch;
		}

		.toolbar-views :global(.btn) {
			flex: 1;
		}

		.toolbar-filters {
			flex-direction: column;
		}

		.toolbar-filters :global(.project-filter-container),
		.toolbar-filters :global(.due-date-filter-container) {
			max-width: 100%;
			width: 100%;
		}

		.subtask-item-card {
			margin-left: 1rem;
		}
	}
</style>
