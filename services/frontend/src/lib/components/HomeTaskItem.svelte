<script lang="ts">
	import {
		getDeadlineTypeLabel,
		getDeadlineTypeColor,
		getDeadlineTypeBgColor
	} from '$lib/utils/deadline';
	import { formatDueDate } from '$lib/utils/dates';
	import type { Todo } from '$lib/types';

	export let task: Todo;
	export let completingTasks: Set<number>;
	export let source: 'today' | 'overdue';
	export let showDueDate: boolean = false;
	export let oncomplete: (event: MouseEvent, taskId: number, source: 'today' | 'overdue') => void;
</script>

<a class="task-item" href="/task/{task.id}">
	<button
		class="complete-btn"
		class:completing={completingTasks.has(task.id)}
		onclick={(e) => oncomplete(e, task.id, source)}
		title="Mark complete"
	></button>
	<span class="priority-dot {task.priority}"></span>
	<div class="task-content">
		<div class="task-title">{task.title}</div>
		<div class="task-meta">
			<span class="task-status {task.status}">{task.status.replace('_', ' ')}</span>
			{#if task.project_name}
				<span class="task-project">{task.project_name}</span>
			{/if}
			{#if showDueDate && task.due_date}
				<span>&middot;</span>
				<span>{formatDueDate(task.due_date)}</span>
			{/if}
			{#if task.deadline_type && task.deadline_type !== 'preferred'}
				<span
					class="deadline-type-pill"
					style="color: {getDeadlineTypeColor(
						task.deadline_type
					)}; background-color: {getDeadlineTypeBgColor(task.deadline_type)}"
				>
					{getDeadlineTypeLabel(task.deadline_type)}
				</span>
			{/if}
			{#each task.tags as tag}
				<span class="task-tag">{tag}</span>
			{/each}
		</div>
	</div>
</a>

<style>
	.task-item {
		display: flex;
		align-items: flex-start;
		gap: var(--space-3);
		padding: 0.625rem 0.5rem;
		border-radius: var(--radius);
		transition: background var(--transition-fast);
		text-decoration: none;
		color: inherit;
	}

	.task-item:hover {
		background: var(--bg-hover);
	}

	.priority-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
		margin-top: 0.375rem;
	}

	.priority-dot.urgent {
		background: var(--error-500);
		box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15);
	}
	.priority-dot.high {
		background: #ea580c;
		box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.15);
	}
	.priority-dot.medium {
		background: var(--warning-500);
		box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15);
	}
	.priority-dot.low {
		background: var(--gray-300);
	}

	.task-content {
		flex: 1;
		min-width: 0;
	}

	.task-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary);
		line-height: 1.4;
	}

	.task-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.125rem;
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.task-project {
		font-weight: 600;
		color: var(--primary-600);
		font-size: 0.6875rem;
	}

	.deadline-type-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.0625rem 0.375rem;
		font-size: 0.625rem;
		font-weight: 600;
		border-radius: 9999px;
	}

	.task-tag {
		padding: 0 0.375rem;
		border-radius: var(--radius);
		background: var(--gray-100);
		color: var(--text-secondary);
		font-size: 0.6875rem;
	}

	.task-status {
		display: inline-flex;
		align-items: center;
		font-size: 0.6875rem;
		font-weight: 500;
		padding: 0.125rem 0.375rem;
		border-radius: var(--radius);
		text-transform: capitalize;
	}

	.task-status.in_progress {
		background: var(--primary-50);
		color: var(--primary-600);
	}

	.task-status.pending {
		background: var(--gray-100);
		color: var(--text-muted);
	}

	.task-status.completed {
		background: var(--success-50);
		color: var(--success-500);
	}

	/* Complete Button */

	.complete-btn {
		width: 32px;
		align-self: stretch;
		border-radius: var(--radius);
		border: none;
		background: transparent;
		cursor: pointer;
		flex-shrink: 0;
		padding: 0;
		position: relative;
		transition: background 0.15s ease;
	}

	.complete-btn::before {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 1.5px solid var(--gray-300);
		transition: all 0.15s ease;
	}

	.complete-btn:hover {
		background: var(--success-50);
	}

	.complete-btn:hover::before {
		border-color: var(--success-500);
	}

	.complete-btn:hover::after {
		content: '✓';
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: 9px;
		color: var(--success-500);
		font-weight: 700;
	}

	.complete-btn.completing {
		background: var(--success-50);
		opacity: 0.6;
		pointer-events: none;
	}

	.complete-btn.completing::before {
		border-color: var(--success-500);
	}
</style>
