<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { todos, pendingTodos, todosByProject } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import { toasts } from '$lib/stores/ui';
	import { api } from '$lib/api/client';
	import TaskDetailPanel from '$lib/components/TaskDetailPanel.svelte';
	import DragDropCalendar from '$lib/components/DragDropCalendar.svelte';
	import ProjectFilter from '$lib/components/ProjectFilter.svelte';
	import DueDateFilter from '$lib/components/DueDateFilter.svelte';
	import DeadlineTypeFilter from '$lib/components/DeadlineTypeFilter.svelte';
	import SearchModal from '$lib/components/SearchModal.svelte';
	import { computeDueDateFilters } from '$lib/utils/dueDateFilter';
	import type { DueDateOption, DueDateFilterValue } from '$lib/utils/dueDateFilter';
	import { getPriorityColor } from '$lib/utils/priority';
	import {
		getDeadlineTypeColor,
		getDeadlineTypeBgColor,
		getDeadlineTypeLabel
	} from '$lib/utils/deadline';
	import { contrastText } from '$lib/utils/colors';
	import { formatDateDisplay } from '$lib/utils/dates';
	import { logger } from '$lib/utils/logger';
	import type { Todo, ApiResponse, DeadlineType } from '$lib/types';

	let currentView: 'list' | 'calendar' = 'calendar';
	let minimizedProjects: Record<string, boolean> = {};
	let taskDetailPanel: TaskDetailPanel;
	let initialLoadComplete = false;
	let searchOpen = false;
	let overdueCount = 0;
	let dueTodayCount = 0;
	let dueThisWeekCount = 0;

	function handleGlobalKeydown(event: KeyboardEvent) {
		if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
			event.preventDefault();
			searchOpen = true;
		}
	}

	function todayStr(): string {
		const d = new Date();
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	function endOfWeekStr(): string {
		const d = new Date();
		const daysUntilSunday = d.getDay() === 0 ? 0 : 7 - d.getDay();
		d.setDate(d.getDate() + daysUntilSunday);
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	async function loadSummaryStats() {
		try {
			const [overdueRes, todayRes, weekRes] = await Promise.all([
				api.get<ApiResponse<Todo[]>>('/api/todos', { params: { status: 'overdue' } }),
				api.get<ApiResponse<Todo[]>>('/api/todos', {
					params: { start_date: todayStr(), end_date: todayStr(), status: 'pending' }
				}),
				api.get<ApiResponse<Todo[]>>('/api/todos', {
					params: { start_date: todayStr(), end_date: endOfWeekStr(), status: 'pending' }
				})
			]);
			overdueCount = overdueRes.meta?.count ?? (overdueRes.data?.length || 0);
			dueTodayCount = todayRes.meta?.count ?? (todayRes.data?.length || 0);
			dueThisWeekCount = weekRes.meta?.count ?? (weekRes.data?.length || 0);
		} catch {
			// Stats are non-critical; silently fail
		}
	}

	// Extract filters from URL
	$: selectedProjectId = $page.url.searchParams.get('project_id')
		? parseInt($page.url.searchParams.get('project_id')!)
		: null;

	$: selectedDueDate = ($page.url.searchParams.get('due_date') as DueDateOption) || 'all';

	$: selectedDeadlineType = ($page.url.searchParams.get('deadline_type') as DeadlineType) || null;

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
			...(selectedDeadlineType && { deadline_type: selectedDeadlineType }),
			...computeDueDateFilters(selectedDueDate)
		});

		// Load summary stats in background
		loadSummaryStats();

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

	function handleDeadlineTypeFilterChange(
		event: CustomEvent<{ deadlineType: DeadlineType | null }>
	) {
		const url = new URL($page.url);

		if (event.detail.deadlineType) {
			url.searchParams.set('deadline_type', event.detail.deadlineType);
		} else {
			url.searchParams.delete('deadline_type');
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
				...(selectedDeadlineType && { deadline_type: selectedDeadlineType }),
				...computeDueDateFilters(selectedDueDate)
			});
			loadSummaryStats();
			toasts.success('Task completed', 5000, {
				label: 'Undo',
				callback: async () => {
					try {
						await todos.updateTodo(todoId, { status: 'pending' });
						await todos.load({
							status: 'pending',
							...(selectedProjectId && { project_id: selectedProjectId }),
							...(selectedDeadlineType && { deadline_type: selectedDeadlineType }),
							...computeDueDateFilters(selectedDueDate)
						});
						loadSummaryStats();
					} catch {
						toasts.error('Failed to undo completion');
					}
				}
			});
		} catch (error) {
			logger.error('Failed to complete todo:', error);
			toasts.error('Failed to complete task');
		}
	}

	async function handleFormSuccess() {
		await todos.load({
			status: 'pending',
			...(selectedProjectId && { project_id: selectedProjectId }),
			...(selectedDeadlineType && { deadline_type: selectedDeadlineType }),
			...computeDueDateFilters(selectedDueDate)
		});
	}

	// Reload todos when filters change (only in browser, after initial load)
	// selectedProjectId, selectedDueDate, and selectedDeadlineType are reactive via URL params
	$: if (browser && initialLoadComplete) {
		// Reference all reactive values to establish dependencies
		const _projectId = selectedProjectId;
		const _dueDate = selectedDueDate;
		const _deadlineType = selectedDeadlineType;
		todos.load({
			status: 'pending',
			...(_projectId ? { project_id: _projectId } : {}),
			...(_deadlineType ? { deadline_type: _deadlineType } : {}),
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

<svelte:window on:keydown={handleGlobalKeydown} />

<SearchModal bind:open={searchOpen} />

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
			<button class="btn btn-secondary btn-med search-trigger" on:click={() => (searchOpen = true)}>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="search-trigger-icon"
				>
					<path
						fill-rule="evenodd"
						d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
						clip-rule="evenodd"
					/>
				</svg>
				Search
				<kbd class="search-shortcut">Ctrl+K</kbd>
			</button>
			<DueDateFilter selected={selectedDueDate} on:change={handleDueDateFilterChange} />
			<DeadlineTypeFilter
				selected={selectedDeadlineType}
				on:change={handleDeadlineTypeFilterChange}
			/>
			<ProjectFilter {selectedProjectId} on:change={handleFilterChange} />
		</div>
	</div>

	<!-- Summary Stats Bar -->
	{#if initialLoadComplete}
		<div class="summary-bar mb-4">
			<span class="summary-stat">
				<span class="summary-count">{$pendingTodos.length}</span> total
			</span>
			{#if overdueCount > 0}
				<span class="summary-stat summary-overdue">
					<span class="summary-count">{overdueCount}</span> overdue
				</span>
			{/if}
			{#if dueTodayCount > 0}
				<span class="summary-stat summary-today">
					<span class="summary-count">{dueTodayCount}</span> due today
				</span>
			{/if}
			{#if dueThisWeekCount > 0}
				<span class="summary-stat summary-week">
					<span class="summary-count">{dueThisWeekCount}</span> this week
				</span>
			{/if}
		</div>
	{/if}

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
												{#if todo.deadline_type && todo.deadline_type !== 'preferred'}
													<span
														class="deadline-type-pill"
														style="color: {getDeadlineTypeColor(
															todo.deadline_type
														)}; background-color: {getDeadlineTypeBgColor(todo.deadline_type)}"
													>
														{getDeadlineTypeLabel(todo.deadline_type)}
													</span>
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

	/* Search trigger button */
	.search-trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
	}

	.search-trigger-icon {
		width: 0.875rem;
		height: 0.875rem;
	}

	.search-shortcut {
		font-size: 0.625rem;
		font-weight: 500;
		padding: 0.0625rem 0.25rem;
		border: 1px solid var(--border-color, #e5e7eb);
		border-radius: var(--radius-sm, 0.25rem);
		color: var(--text-muted, #9ca3af);
		background: var(--bg-page, #f9fafb);
		margin-left: 0.25rem;
	}

	/* Summary stats bar */
	.summary-bar {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.summary-stat {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--text-muted, #6b7280);
		padding: 0.25rem 0.625rem;
		border-radius: 9999px;
		background: var(--gray-100, #f3f4f6);
	}

	.summary-count {
		font-weight: 700;
		color: var(--text-secondary, #374151);
	}

	.summary-overdue {
		background: var(--error-50, #fef2f2);
		color: var(--error-600, #dc2626);
	}

	.summary-overdue .summary-count {
		color: var(--error-700, #b91c1c);
	}

	.summary-today {
		background: var(--primary-50, #eff6ff);
		color: var(--primary-600, #2563eb);
	}

	.summary-today .summary-count {
		color: var(--primary-700, #1d4ed8);
	}

	.summary-week {
		background: var(--warning-50, #fffbeb);
		color: var(--warning-600, #d97706);
	}

	.summary-week .summary-count {
		color: var(--warning-700, #b45309);
	}

	.deadline-type-pill {
		display: inline-block;
		padding: 0.0625rem 0.375rem;
		font-size: 0.625rem;
		font-weight: 600;
		border-radius: 9999px;
		margin-left: 0.25rem;
		vertical-align: middle;
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
		background-color: var(--primary-50);
		color: var(--primary-600);
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
