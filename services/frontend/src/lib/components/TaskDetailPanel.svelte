<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import TodoForm from './TodoForm.svelte';
	import SubtaskList from './SubtaskList.svelte';
	import DependencyList from './DependencyList.svelte';
	import AttachmentList from './AttachmentList.svelte';
	import { getPriorityColor } from '$lib/utils/priority';
	import { formatDateDisplay } from '$lib/utils/dates';
	import { todos } from '$lib/stores/todos';
	import type { Todo } from '$lib/types';

	export let show = false;
	export let todo: Todo | null = null;

	let mode: 'view' | 'edit' | 'create' = 'view';
	let todoForm: TodoForm;

	const dispatch = createEventDispatcher();

	export function open(selectedTodo: Todo) {
		todo = selectedTodo;
		mode = 'view';
		show = true;
	}

	export function openEdit(selectedTodo: Todo) {
		todo = selectedTodo;
		mode = 'edit';
		show = true;
	}

	export function openCreate() {
		todo = null;
		mode = 'create';
		show = true;
		if (todoForm) todoForm.reset();
	}

	export function close() {
		show = false;
		setTimeout(() => {
			todo = null;
			mode = 'view';
			if (todoForm) todoForm.reset();
		}, 300); // Wait for slide-out animation
	}

	function handleBackdropClick() {
		close();
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && show) {
			close();
		}
	}

	function handleEdit() {
		mode = 'edit';
	}

	function handleComplete() {
		dispatch('complete', todo?.id);
		close();
	}

	function handleFormSuccess() {
		dispatch('formSuccess');
		close();
	}

	function switchToView() {
		mode = 'view';
	}

	async function handleSubtaskChange() {
		// Refresh the todo to get updated subtasks
		if (todo) {
			try {
				const updatedTodo = await todos.getById(todo.id);
				todo = updatedTodo;
				dispatch('formSuccess');
			} catch (error) {
				console.error('Failed to refresh todo:', error);
			}
		}
	}

	async function handleDependencyChange() {
		// Refresh the todo to get updated dependencies
		if (todo) {
			try {
				const updatedTodo = await todos.getById(todo.id);
				todo = updatedTodo;
				dispatch('formSuccess');
			} catch (error) {
				console.error('Failed to refresh todo:', error);
			}
		}
	}

	$: panelTitle =
		mode === 'create' ? 'Create Task' : mode === 'edit' ? 'Edit Task' : 'Task Details';
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
	<div class="panel-backdrop" on:click={handleBackdropClick} role="dialog" aria-modal="true">
		<div class="panel-container" on:click|stopPropagation role="document">
			<div class="panel-header">
				<div class="flex items-center gap-3">
					{#if mode === 'edit'}
						<button
							class="back-btn"
							on:click={switchToView}
							aria-label="Back to details"
							title="Back to details"
						>
							←
						</button>
					{/if}
					<h2>{panelTitle}</h2>
				</div>
				<button class="close-btn" on:click={close} aria-label="Close panel">&times;</button>
			</div>

			{#if mode === 'view' && todo}
				<div class="panel-body">
					<!-- Title -->
					<div class="detail-section">
						<div class="flex items-center gap-2 mb-2">
							<span
								class="w-3 h-3 rounded-full flex-shrink-0"
								style="background-color: {getPriorityColor(todo.priority)}"
							></span>
							<h3 class="text-xl font-semibold text-gray-900">{todo.title}</h3>
						</div>
					</div>

					<!-- Description -->
					{#if todo.description}
						<div class="detail-section">
							<label class="detail-label">Description</label>
							<p class="detail-text">{todo.description}</p>
						</div>
					{/if}

					<!-- Project -->
					{#if todo.project_name}
						<div class="detail-section">
							<label class="detail-label">Project</label>
							<div class="flex items-center gap-2">
								{#if todo.project_color}
									<span class="w-3 h-3 rounded-sm" style="background-color: {todo.project_color}"
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
					<div class="detail-section">
						<label class="detail-label">Created</label>
						<span class="detail-text text-xs">{new Date(todo.created_at).toLocaleString()}</span>
					</div>

					{#if todo.updated_at !== todo.created_at}
						<div class="detail-section">
							<label class="detail-label">Last Updated</label>
							<span class="detail-text text-xs">{new Date(todo.updated_at).toLocaleString()}</span>
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

					<!-- Subtasks (only show for non-subtask todos) -->
					{#if !todo.parent_id}
						<SubtaskList
							todoId={todo.id}
							subtasks={todo.subtasks || []}
							on:subtaskAdded={handleSubtaskChange}
							on:subtaskCompleted={handleSubtaskChange}
							on:subtaskDeleted={handleSubtaskChange}
						/>
					{/if}

					<!-- Dependencies (only show for non-subtask todos) -->
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
				</div>

				<!-- Actions -->
				<div class="panel-footer">
					<button class="btn btn-secondary" on:click={handleEdit}>Edit Task</button>
					{#if todo.status === 'pending' || todo.status === 'in_progress'}
						<button class="btn btn-success" on:click={handleComplete}>Mark Complete</button>
					{/if}
				</div>
			{:else if mode === 'edit' || mode === 'create'}
				<div class="panel-body">
					<TodoForm bind:this={todoForm} bind:editingTodo={todo} on:success={handleFormSuccess} />
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.panel-backdrop {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: var(--bg-overlay);
		z-index: 1000;
		display: flex;
		justify-content: flex-end;
		animation: fadeIn 0.2s ease-out;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	.panel-container {
		background: var(--bg-card);
		width: 100%;
		max-width: 500px;
		height: 100vh;
		overflow-y: auto;
		box-shadow: var(--shadow-lg);
		display: flex;
		flex-direction: column;
		animation: slideIn 0.3s ease-out;
	}

	@keyframes slideIn {
		from {
			transform: translateX(100%);
		}
		to {
			transform: translateX(0);
		}
	}

	.panel-header {
		padding: 1.5rem;
		border-bottom: 1px solid var(--border-color);
		display: flex;
		justify-content: space-between;
		align-items: center;
		position: sticky;
		top: 0;
		background: var(--bg-card);
		z-index: 10;
	}

	.panel-header h2 {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.close-btn,
	.back-btn {
		background: none;
		border: none;
		font-size: 2rem;
		color: var(--text-muted);
		cursor: pointer;
		padding: 0;
		width: 2rem;
		height: 2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.25rem;
		transition: all var(--transition-base);
	}

	.close-btn:hover,
	.back-btn:hover {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.back-btn {
		font-size: 1.5rem;
		font-weight: 600;
	}

	.panel-body {
		flex: 1;
		padding: 1.5rem;
		overflow-y: auto;
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

	.tag {
		display: inline-block;
		padding: 0.25rem 0.75rem;
		background-color: var(--tag-bg);
		color: var(--tag-text);
		font-size: 0.75rem;
		border-radius: 9999px;
		font-weight: 500;
	}

	.panel-footer {
		padding: 1.5rem;
		border-top: 1px solid var(--border-color);
		display: flex;
		gap: 0.75rem;
		background: var(--bg-card);
		position: sticky;
		bottom: 0;
	}

	@media (max-width: 640px) {
		.panel-container {
			max-width: 100%;
		}
	}
</style>
