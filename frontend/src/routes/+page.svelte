<script lang="ts">
	import { onMount } from 'svelte';
	import { todos, pendingTodos, todosByProject } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import TodoModal from '$lib/components/TodoModal.svelte';
	import DragDropCalendar from '$lib/components/DragDropCalendar.svelte';
	import type { Todo } from '$lib/types';

	let currentView: 'list' | 'calendar' = 'calendar';
	let minimizedProjects: Record<string, boolean> = {};
	let editingTodo: Todo | null = null;
	let showModal = false;

	onMount(async () => {
		// Load todos and projects
		await Promise.all([
			todos.loadTodos({ status: 'pending' }),
			projects.loadProjects()
		]);

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
		const projectId = `project-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
		minimizedProjects[projectId] = !minimizedProjects[projectId];
		localStorage.setItem('minimized-projects', JSON.stringify(minimizedProjects));
	}

	function isProjectMinimized(projectName: string): boolean {
		const projectId = `project-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
		return minimizedProjects[projectId] || false;
	}

	function openEditModal(todo: Todo) {
		editingTodo = todo;
		showModal = true;
	}

	async function handleCompleteTodo(todoId: number) {
		try {
			await todos.completeTodo(todoId);
			// Reload todos after completion
			await todos.loadTodos({ status: 'pending' });
		} catch (error) {
			console.error('Failed to complete todo:', error);
			alert('Failed to complete todo');
		}
	}

	function formatDateForDisplay(dateStr: string | null): string {
		if (!dateStr) return '';
		const [year, month, day] = dateStr.split('-').map(Number);
		const date = new Date(year, month - 1, day);
		return date.toLocaleDateString();
	}

	// Group todos by project for list view
	$: groupedTodos = $pendingTodos.reduce((acc, todo) => {
		const projectName = todo.project_name || 'No Project';
		if (!acc[projectName]) acc[projectName] = [];
		acc[projectName].push(todo);
		return acc;
	}, {} as Record<string, Todo[]>);

	// Sort project names
	$: sortedProjectNames = Object.keys(groupedTodos).sort();
</script>

<svelte:head>
	<title>Todo Manager</title>
</svelte:head>

<main class="container py-8">
	<h1 class="text-3xl font-bold text-gray-900 mb-8">Todo Manager</h1>

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

	<!-- Todo Modal -->
	<TodoModal bind:show={showModal} todo={editingTodo} on:save={() => todos.loadTodos({ status: 'pending' })} />

	<!-- List View -->
	{#if currentView === 'list'}
		<div id="list-view">
			<div id="todo-lists" class="grid grid-cols-1 md:grid-cols-2 gap-6">
				{#each sortedProjectNames as projectName}
					{@const projectTodos = groupedTodos[projectName]}
					{@const projectId = `project-${projectName.replace(/\s+/g, '-').toLowerCase()}`}
					{@const isMinimized = isProjectMinimized(projectName)}
					<div class="card">
						<div class="flex items-center justify-between mb-3">
							<h3 class="font-semibold text-lg text-gray-800">{projectName}</h3>
							<button
								on:click={() => toggleProject(projectName)}
								class="btn btn-sm btn-secondary project-toggle"
								title={isMinimized ? 'Expand' : 'Minimize' + ' project'}
							>
								{isMinimized ? '▲' : '▼'}
							</button>
						</div>
						<div class="space-y-2 {isMinimized ? 'hidden' : ''}">
							{#each projectTodos as todo}
								<div class="flex items-center justify-between p-3 border rounded">
									<div class="flex-1">
										<div class="font-medium">{todo.title}</div>
										<div class="text-sm text-gray-600">{todo.description || ''}</div>
										<div class="text-xs text-gray-500 mt-1">
											Priority: {todo.priority}
											{#if todo.due_date}
												| Due: {formatDateForDisplay(todo.due_date)}
											{/if}
										</div>
									</div>
									<div class="flex gap-3 ml-4">
										<button
											on:click={() => openEditModal(todo)}
											class="btn btn-secondary btn-sm"
											title="Edit todo"
										>
											✏️
										</button>
										<button
											on:click={() => handleCompleteTodo(todo.id)}
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
			<DragDropCalendar on:editTodo={(e) => openEditModal(e.detail)} />
		</div>
	{/if}
</main>
