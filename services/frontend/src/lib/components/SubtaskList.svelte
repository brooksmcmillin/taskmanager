<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import { getPriorityColor } from '$lib/utils/priority';
	import type { Subtask, SubtaskCreate } from '$lib/types';

	export let todoId: number;
	export let subtasks: Subtask[] = [];

	let showAddForm = false;
	let newSubtaskTitle = '';
	let newSubtaskPriority: 'low' | 'medium' | 'high' | 'urgent' = 'medium';
	let isSubmitting = false;

	const dispatch = createEventDispatcher();

	async function handleAddSubtask() {
		if (!newSubtaskTitle.trim() || isSubmitting) return;

		isSubmitting = true;
		try {
			const subtaskData: SubtaskCreate = {
				title: newSubtaskTitle.trim(),
				priority: newSubtaskPriority
			};
			await todos.addSubtask(todoId, subtaskData);
			newSubtaskTitle = '';
			newSubtaskPriority = 'medium';
			showAddForm = false;
			dispatch('subtaskAdded');
		} catch (error) {
			console.error('Failed to add subtask:', error);
		} finally {
			isSubmitting = false;
		}
	}

	async function handleCompleteSubtask(subtaskId: number) {
		try {
			await todos.completeSubtask(todoId, subtaskId);
			dispatch('subtaskCompleted', subtaskId);
		} catch (error) {
			console.error('Failed to complete subtask:', error);
		}
	}

	async function handleDeleteSubtask(subtaskId: number) {
		if (!confirm('Delete this subtask?')) return;
		try {
			await todos.removeSubtask(todoId, subtaskId);
			dispatch('subtaskDeleted', subtaskId);
		} catch (error) {
			console.error('Failed to delete subtask:', error);
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			handleAddSubtask();
		} else if (event.key === 'Escape') {
			showAddForm = false;
			newSubtaskTitle = '';
		}
	}

	$: completedCount = subtasks.filter((s) => s.status === 'completed').length;
	$: totalCount = subtasks.length;
	$: progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;
</script>

<div class="subtask-list">
	<div class="subtask-header">
		<h4 class="subtask-title">
			Subtasks
			{#if totalCount > 0}
				<span class="subtask-count">({completedCount}/{totalCount})</span>
			{/if}
		</h4>
		{#if !showAddForm}
			<button class="add-subtask-btn" on:click={() => (showAddForm = true)} title="Add subtask">
				+
			</button>
		{/if}
	</div>

	{#if totalCount > 0}
		<div class="progress-bar">
			<div class="progress-fill" style="width: {progressPercent}%"></div>
		</div>
	{/if}

	{#if showAddForm}
		<div class="add-subtask-form">
			<div class="form-row">
				<input
					type="text"
					bind:value={newSubtaskTitle}
					placeholder="Enter subtask title..."
					class="subtask-input"
					on:keydown={handleKeydown}
					autofocus
				/>
				<select bind:value={newSubtaskPriority} class="priority-select">
					<option value="low">Low</option>
					<option value="medium">Medium</option>
					<option value="high">High</option>
					<option value="urgent">Urgent</option>
				</select>
			</div>
			<div class="form-actions">
				<button class="btn btn-sm btn-primary" on:click={handleAddSubtask} disabled={isSubmitting}>
					{isSubmitting ? 'Adding...' : 'Add'}
				</button>
				<button
					class="btn btn-sm btn-secondary"
					on:click={() => {
						showAddForm = false;
						newSubtaskTitle = '';
					}}
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}

	<ul class="subtask-items">
		{#each subtasks as subtask (subtask.id)}
			<li class="subtask-item" class:completed={subtask.status === 'completed'}>
				<button
					class="checkbox"
					class:checked={subtask.status === 'completed'}
					on:click={() => handleCompleteSubtask(subtask.id)}
					disabled={subtask.status === 'completed'}
					title={subtask.status === 'completed' ? 'Completed' : 'Mark as complete'}
				>
					{#if subtask.status === 'completed'}
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
							<path d="M5 13l4 4L19 7" />
						</svg>
					{/if}
				</button>
				<div class="subtask-content">
					<a href="/task/{subtask.id}" class="subtask-id" title="Open task #{subtask.id}"
						>#{subtask.id}</a
					>
					<span class="subtask-text">{subtask.title}</span>
					<span
						class="priority-dot"
						style="background-color: {getPriorityColor(subtask.priority)}"
						title="{subtask.priority} priority"
					></span>
				</div>
				<button
					class="delete-btn"
					on:click={() => handleDeleteSubtask(subtask.id)}
					title="Delete subtask"
				>
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</li>
		{/each}
	</ul>

	{#if subtasks.length === 0 && !showAddForm}
		<p class="no-subtasks">No subtasks yet. Click + to add one.</p>
	{/if}
</div>

<style>
	.subtask-list {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--border-color);
	}

	.subtask-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.subtask-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-secondary);
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.subtask-count {
		font-weight: 400;
		color: var(--text-muted);
		margin-left: 0.5rem;
	}

	.add-subtask-btn {
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

	.add-subtask-btn:hover {
		border-color: var(--primary-500);
		color: var(--primary-500);
		background-color: var(--primary-50);
	}

	.progress-bar {
		height: 4px;
		background-color: var(--border-color);
		border-radius: 2px;
		margin-bottom: 1rem;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background-color: #10b981;
		border-radius: 2px;
		transition: width 0.3s ease;
	}

	.add-subtask-form {
		background-color: var(--bg-page);
		border-radius: 0.5rem;
		padding: 0.75rem;
		margin-bottom: 1rem;
	}

	.form-row {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}

	.subtask-input {
		flex: 1;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--gray-300);
		border-radius: 0.375rem;
		font-size: 0.875rem;
		background-color: var(--bg-input);
		color: var(--text-primary);
	}

	.subtask-input:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
	}

	.priority-select {
		padding: 0.5rem;
		border: 1px solid var(--gray-300);
		border-radius: 0.375rem;
		font-size: 0.875rem;
		background: var(--bg-input);
		color: var(--text-primary);
	}

	.form-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
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

	.subtask-items {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.subtask-item {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border-light);
	}

	.subtask-item:last-child {
		border-bottom: none;
	}

	.subtask-item.completed .subtask-text {
		text-decoration: line-through;
		color: var(--text-muted);
	}

	.checkbox {
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		border: 2px solid var(--gray-300);
		background: var(--bg-card);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: all var(--transition-base);
	}

	.checkbox:hover:not(:disabled) {
		border-color: var(--success-500);
	}

	.checkbox.checked {
		background-color: var(--success-500);
		border-color: var(--success-500);
	}

	.checkbox.checked svg {
		width: 0.75rem;
		height: 0.75rem;
		color: white;
	}

	.checkbox:disabled {
		cursor: default;
	}

	.subtask-content {
		flex: 1;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}

	.subtask-id {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-muted);
		text-decoration: none;
		font-family: monospace;
		flex-shrink: 0;
		transition: color var(--transition-fast);
	}

	.subtask-id:hover {
		color: var(--primary-600);
		text-decoration: underline;
	}

	.subtask-text {
		font-size: 0.875rem;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.priority-dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		flex-shrink: 0;
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

	.subtask-item:hover .delete-btn {
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

	.no-subtasks {
		font-size: 0.875rem;
		color: var(--text-muted);
		text-align: center;
		padding: 1rem 0;
		margin: 0;
	}
</style>
