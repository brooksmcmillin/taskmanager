<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import TodoForm from '$lib/components/TodoForm.svelte';
	import SubtaskList from '$lib/components/SubtaskList.svelte';
	import DependencyList from '$lib/components/DependencyList.svelte';
	import AttachmentList from '$lib/components/AttachmentList.svelte';
	import CommentList from '$lib/components/CommentList.svelte';
	import { getPriorityColor } from '$lib/utils/priority';
	import { formatDateDisplay } from '$lib/utils/dates';
	import { todos } from '$lib/stores/todos';
	import { projects } from '$lib/stores/projects';
	import { toasts } from '$lib/stores/ui';
	import type { Todo } from '$lib/types';

	let todo: Todo | null = null;
	let loading = true;
	let error = '';
	let mode: 'view' | 'edit' = 'view';
	let todoForm: TodoForm;

	$: todoId = parseInt($page.params.id ?? '0');

	onMount(async () => {
		await projects.load();
		await loadTodo();
	});

	async function loadTodo() {
		loading = true;
		error = '';
		try {
			todo = await todos.getById(todoId);
		} catch (e) {
			error = 'Task not found';
		} finally {
			loading = false;
		}
	}

	function handleEdit() {
		mode = 'edit';
	}

	function switchToView() {
		mode = 'view';
	}

	async function handleComplete() {
		if (!todo) return;
		try {
			await todos.complete(todo.id);
			toasts.show('Task marked as complete', 'success');
			await loadTodo();
		} catch (e) {
			toasts.show('Failed to complete task', 'error');
		}
	}

	async function handleUncomplete() {
		if (!todo) return;
		try {
			await todos.updateTodo(todo.id, { status: 'pending' });
			toasts.show('Task marked as incomplete', 'success');
			await loadTodo();
		} catch (e) {
			toasts.show('Failed to update task', 'error');
		}
	}

	async function handleFormSuccess() {
		await loadTodo();
		mode = 'view';
	}

	async function handleSubtaskChange() {
		await loadTodo();
	}

	async function handleDependencyChange() {
		await loadTodo();
	}
</script>

<svelte:head>
	<title>{todo ? todo.title : 'Task'} - Todo Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="task-page">
		<!-- Back link -->
		<a href="/" class="back-link">&larr; Back to tasks</a>

		{#if loading}
			<div class="loading-state">Loading task...</div>
		{:else if error}
			<div class="error-state">
				<p>{error}</p>
				<a href="/" class="btn btn-secondary">Back to tasks</a>
			</div>
		{:else if todo}
			<div class="task-page-header">
				<h1>
					{#if mode === 'edit'}
						Edit Task
					{:else}
						Task Details
					{/if}
				</h1>
				{#if mode === 'edit'}
					<button class="btn btn-secondary btn-med" on:click={switchToView}>Cancel</button>
				{/if}
			</div>

			{#if mode === 'view'}
				<div class="task-content">
					<div class="task-main">
						<!-- Parent Task -->
						{#if todo.parent_task}
							<div class="detail-section">
								<label class="detail-label">Parent Task</label>
								<a href="/task/{todo.parent_task.id}" class="parent-task-link">
									<span class="parent-task-id">#{todo.parent_task.id}</span>
									{todo.parent_task.title}
								</a>
							</div>
						{/if}

						<!-- Title -->
						<div class="detail-section">
							<div class="flex items-center gap-2 mb-2">
								<span
									class="w-3 h-3 rounded-full flex-shrink-0"
									style="background-color: {getPriorityColor(todo.priority)}"
								></span>
								<h2 class="task-title">{todo.title}</h2>
							</div>
						</div>

						<!-- Description -->
						{#if todo.description}
							<div class="detail-section">
								<label class="detail-label">Description</label>
								<p class="detail-text">{todo.description}</p>
							</div>
						{/if}

						<!-- Metadata grid -->
						<div class="metadata-grid">
							<!-- Project -->
							{#if todo.project_name}
								<div class="detail-section">
									<label class="detail-label">Project</label>
									<div class="flex items-center gap-2">
										{#if todo.project_color}
											<span
												class="w-3 h-3 rounded-sm"
												style="background-color: {todo.project_color}"
											></span>
										{/if}
										<span class="detail-text">{todo.project_name}</span>
									</div>
								</div>
							{/if}

							<!-- Priority -->
							<div class="detail-section">
								<label class="detail-label">Priority</label>
								<div class="flex items-center gap-2">
									<span
										class="w-2 h-2 rounded-full"
										style="background-color: {getPriorityColor(todo.priority)}"
									></span>
									<span class="detail-text capitalize">{todo.priority}</span>
								</div>
							</div>

							<!-- Status -->
							<div class="detail-section">
								<label class="detail-label">Status</label>
								<span class="detail-text capitalize">{todo.status.replace('_', ' ')}</span>
							</div>

							<!-- Due Date -->
							<div class="detail-section">
								<label class="detail-label">Due Date</label>
								<span class="detail-text">{formatDateDisplay(todo.due_date, 'Not set')}</span>
							</div>
						</div>

						<!-- Tags -->
						{#if todo.tags && todo.tags.length > 0}
							<div class="detail-section">
								<label class="detail-label">Tags</label>
								<div class="flex flex-wrap gap-2">
									{#each todo.tags as tag}
										<span class="tag">{tag}</span>
									{/each}
								</div>
							</div>
						{/if}

						<!-- Estimated Hours -->
						{#if todo.estimated_hours}
							<div class="detail-section">
								<label class="detail-label">Estimated Hours</label>
								<span class="detail-text">{todo.estimated_hours}h</span>
							</div>
						{/if}

						<!-- Actual Hours -->
						{#if todo.actual_hours}
							<div class="detail-section">
								<label class="detail-label">Actual Hours</label>
								<span class="detail-text">{todo.actual_hours}h</span>
							</div>
						{/if}

						<!-- Context -->
						{#if todo.context}
							<div class="detail-section">
								<label class="detail-label">Context</label>
								<p class="detail-text">{todo.context}</p>
							</div>
						{/if}

						<!-- Timestamps -->
						<div class="timestamps">
							<div class="detail-section">
								<label class="detail-label">Created</label>
								<span class="detail-text text-xs">{new Date(todo.created_at).toLocaleString()}</span
								>
							</div>

							{#if todo.updated_at !== todo.created_at}
								<div class="detail-section">
									<label class="detail-label">Last Updated</label>
									<span class="detail-text text-xs"
										>{new Date(todo.updated_at).toLocaleString()}</span
									>
								</div>
							{/if}

							{#if todo.completed_date}
								<div class="detail-section">
									<label class="detail-label">Completed</label>
									<span class="detail-text text-xs"
										>{new Date(todo.completed_date).toLocaleString()}</span
									>
								</div>
							{/if}
						</div>

						<!-- Subtasks -->
						{#if !todo.parent_id}
							<SubtaskList
								todoId={todo.id}
								subtasks={todo.subtasks || []}
								on:subtaskAdded={handleSubtaskChange}
								on:subtaskCompleted={handleSubtaskChange}
								on:subtaskDeleted={handleSubtaskChange}
							/>
						{/if}

						<!-- Dependencies -->
						{#if !todo.parent_id}
							<DependencyList
								todoId={todo.id}
								dependencies={todo.dependencies || []}
								dependents={todo.dependents || []}
								on:dependencyAdded={handleDependencyChange}
								on:dependencyRemoved={handleDependencyChange}
							/>
						{/if}

						<!-- Attachments -->
						<AttachmentList todoId={todo.id} attachments={todo.attachments || []} />

						<!-- Comments -->
						<CommentList todoId={todo.id} comments={todo.comments || []} />
					</div>

					<!-- Actions -->
					<div class="task-actions">
						<button class="btn btn-secondary" on:click={handleEdit}>Edit Task</button>
						{#if todo.status === 'pending' || todo.status === 'in_progress'}
							<button class="btn btn-success" on:click={handleComplete}>Mark Complete</button>
						{:else if todo.status === 'completed'}
							<button class="btn btn-warning" on:click={handleUncomplete}>Mark Incomplete</button>
						{/if}
					</div>
				</div>
			{:else if mode === 'edit'}
				<div class="task-content">
					<div class="task-form-wrapper">
						<TodoForm bind:this={todoForm} bind:editingTodo={todo} on:success={handleFormSuccess} />
					</div>
				</div>
			{/if}
		{/if}
	</div>
</main>

<style>
	.task-page {
		max-width: 800px;
		margin: 0 auto;
	}

	.back-link {
		display: inline-block;
		color: var(--text-secondary);
		text-decoration: none;
		font-size: 0.875rem;
		margin-bottom: 1.5rem;
		transition: color var(--transition-fast);
	}

	.back-link:hover {
		color: var(--primary-600);
	}

	.task-page-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 2rem;
	}

	.task-page-header h1 {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.loading-state,
	.error-state {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--text-secondary);
	}

	.error-state p {
		margin-bottom: 1.5rem;
		font-size: 1.125rem;
	}

	.task-content {
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius-lg);
		overflow: hidden;
	}

	.task-main {
		padding: 2rem;
	}

	.task-title {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.detail-section {
		margin-bottom: 1.5rem;
	}

	.detail-label {
		display: block;
		font-size: 0.6875rem;
		font-weight: 700;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		margin-bottom: 0.5rem;
	}

	.detail-text {
		color: var(--text-primary);
		font-size: 0.875rem;
		line-height: 1.5;
		white-space: pre-wrap;
	}

	.metadata-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 0;
	}

	.timestamps {
		display: flex;
		flex-wrap: wrap;
		gap: 0 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border-light);
	}

	.tag {
		display: inline-block;
		padding: 0.25rem 0.75rem;
		background-color: var(--tag-bg);
		color: var(--tag-text);
		font-size: 0.75rem;
		border-radius: 9999px;
		font-weight: 500;
	}

	.task-actions {
		padding: 1.5rem 2rem;
		border-top: 1px solid var(--border-color);
		display: flex;
		gap: 0.75rem;
	}

	.task-form-wrapper {
		padding: 2rem;
	}

	.parent-task-link {
		display: inline-flex;
		align-items: center;
		gap: 0.375rem;
		color: var(--text-primary);
		text-decoration: none;
		font-size: 0.875rem;
		transition: color var(--transition-fast);
	}

	.parent-task-link:hover {
		color: var(--primary-600);
	}

	.parent-task-id {
		font-family: monospace;
		color: var(--text-muted);
		font-weight: 600;
	}

	.parent-task-link:hover .parent-task-id {
		color: var(--primary-600);
	}

	@media (max-width: 640px) {
		.task-main {
			padding: 1.5rem;
		}

		.task-actions {
			padding: 1.5rem;
		}

		.task-form-wrapper {
			padding: 1.5rem;
		}

		.metadata-grid {
			grid-template-columns: 1fr 1fr;
		}
	}
</style>
