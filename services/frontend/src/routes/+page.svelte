<script lang="ts">
	import { onMount } from 'svelte';
	import { todos, pendingTodos, todosByProject } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import TaskDetailPanel from '$lib/components/TaskDetailPanel.svelte';
	import DragDropCalendar from '$lib/components/DragDropCalendar.svelte';
	import { getPriorityColor } from '$lib/utils/priority';
	import { formatDateDisplay } from '$lib/utils/dates';
	import type { Todo } from '$lib/types';

	let currentView: 'list' | 'calendar' = 'calendar';
	let minimizedProjects: Record<string, boolean> = {};
	let taskDetailPanel: TaskDetailPanel;

	function getProjectId(projectName: string): string {
		return `project-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
	}

	onMount(async () => {
		// Load todos and projects
		await Promise.all([todos.load({ status: 'pending' }), projects.load()]);

		// Load minimized state from localStorage
		const stored = localStorage.getItem('minimized-projects');
		if (stored) {
			try {
				minimizedProjects = JSON.parse(stored);
			} catch (e) {
				minimizedProjects = {};
			}
		}
	});

	function toggleProject(projectName: string) {
		const projectId = getProjectId(projectName);
		minimizedProjects[projectId] = !minimizedProjects[projectId];
		localStorage.setItem('minimized-projects', JSON.stringify(minimizedProjects));
	}

	function isProjectMinimized(projectName: string): boolean {
		return minimizedProjects[getProjectId(projectName)] || false;
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
			// Reload todos after completion
			await todos.load({ status: 'pending' });
		} catch (error) {
			console.error('Failed to complete todo:', error);
			alert('Failed to complete todo');
		}
	}

	async function handleFormSuccess() {
		await todos.load({ status: 'pending' });
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
	<!-- View Toggle -->
	<div class="flex justify-center mb-6">
		<div class="flex gap-4">
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
			<DragDropCalendar on:editTodo={(e) => openTaskDetail(e.detail)} />
		</div>
	{/if}
</main>
