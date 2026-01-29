<script lang="ts">
	import { onMount } from 'svelte';
	import { recurringTasks } from '$lib/stores/recurringTasks';
	import { projects } from '$lib/stores/projects';
	import RecurringTaskModal from '$lib/components/RecurringTaskModal.svelte';
	import type { RecurringTask, Project } from '$lib/types';

	let taskModal: RecurringTaskModal;
	let showInactive = false;

	// Use auto-subscription with derived value to avoid memory leaks
	$: projectMap = $projects.reduce(
		(acc, project) => {
			acc[project.id] = project;
			return acc;
		},
		{} as Record<number, Project>
	);

	onMount(async () => {
		await Promise.all([recurringTasks.load(!showInactive), projects.load()]);
	});

	async function toggleShowInactive() {
		showInactive = !showInactive;
		await recurringTasks.load(!showInactive);
	}

	function openEditModal(task: RecurringTask) {
		taskModal.openEdit(task);
	}

	function openAddModal() {
		taskModal.open();
	}

	function getFrequencyLabel(task: RecurringTask): string {
		const interval = task.interval_value;
		switch (task.frequency) {
			case 'daily':
				return interval === 1 ? 'Daily' : `Every ${interval} days`;
			case 'weekly':
				if (task.weekdays && task.weekdays.length > 0) {
					const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
					const selectedDays = task.weekdays.map((d) => days[d]).join(', ');
					return interval === 1
						? `Weekly on ${selectedDays}`
						: `Every ${interval} weeks on ${selectedDays}`;
				}
				return interval === 1 ? 'Weekly' : `Every ${interval} weeks`;
			case 'monthly':
				const dayText = task.day_of_month ? ` on day ${task.day_of_month}` : '';
				return interval === 1 ? `Monthly${dayText}` : `Every ${interval} months${dayText}`;
			case 'yearly':
				return interval === 1 ? 'Yearly' : `Every ${interval} years`;
			default:
				return task.frequency;
		}
	}

	function formatDate(dateString: string): string {
		return new Date(dateString).toLocaleDateString();
	}

	function getPriorityClass(priority: string): string {
		switch (priority) {
			case 'urgent':
				return 'priority-urgent';
			case 'high':
				return 'priority-high';
			case 'medium':
				return 'priority-medium';
			case 'low':
				return 'priority-low';
			default:
				return '';
		}
	}

	async function handleSave() {
		await recurringTasks.load(!showInactive);
	}
</script>

<svelte:head>
	<title>Recurring Tasks</title>
</svelte:head>

<main class="container py-8">
	<RecurringTaskModal bind:this={taskModal} on:save={handleSave} />

	<div class="max-w-4xl mx-auto">
		<div class="flex justify-between items-center mb-6">
			<h2 class="text-xl font-semibold">Recurring Tasks</h2>
			<div class="flex items-center gap-4">
				<label class="toggle-label">
					<input
						type="checkbox"
						checked={showInactive}
						on:change={toggleShowInactive}
						class="toggle-checkbox"
					/>
					<span class="toggle-text">Show inactive</span>
				</label>
				<button class="btn btn-primary" on:click={openAddModal}> Add Recurring Task </button>
			</div>
		</div>

		<div class="recurring-tasks-list">
			{#if $recurringTasks.length === 0}
				<div class="empty-state">
					<p class="text-gray-500">No recurring tasks yet.</p>
					<p class="text-gray-400 text-sm mt-2">
						Create a recurring task to automatically generate todos on a schedule.
					</p>
				</div>
			{:else}
				{#each $recurringTasks as task}
					<div
						class="card recurring-task-card"
						class:inactive={!task.is_active}
						on:click={() => openEditModal(task)}
						on:keydown={(e) => e.key === 'Enter' && openEditModal(task)}
						role="button"
						tabindex="0"
					>
						<div class="task-header">
							<h3 class="task-title">{task.title}</h3>
							<span class="priority-badge {getPriorityClass(task.priority)}">{task.priority}</span>
						</div>

						<div class="task-meta">
							<span class="frequency-badge">{getFrequencyLabel(task)}</span>
							{#if task.project_id && projectMap[task.project_id]}
								<span
									class="project-badge"
									style="background-color: {projectMap[task.project_id]
										.color}20; color: {projectMap[task.project_id].color}"
								>
									{projectMap[task.project_id].name}
								</span>
							{/if}
							{#if !task.is_active}
								<span class="inactive-badge">Inactive</span>
							{/if}
						</div>

						<div class="task-dates">
							<span class="date-item">
								<span class="date-label">Next:</span>
								{formatDate(task.next_due_date)}
							</span>
							{#if task.end_date}
								<span class="date-item">
									<span class="date-label">Until:</span>
									{formatDate(task.end_date)}
								</span>
							{/if}
						</div>

						{#if task.description}
							<p class="task-description">{task.description}</p>
						{/if}

						{#if task.tags && task.tags.length > 0}
							<div class="task-tags">
								{#each task.tags as tag}
									<span class="tag">{tag}</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>

<style>
	.recurring-tasks-list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.empty-state {
		text-align: center;
		padding: 3rem;
		background-color: #f9fafb;
		border-radius: 0.5rem;
	}

	.recurring-task-card {
		cursor: pointer;
		transition: all 0.15s ease-in-out;
	}

	.recurring-task-card:hover {
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
		transform: translateY(-2px);
	}

	.recurring-task-card.inactive {
		opacity: 0.6;
	}

	.task-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 0.75rem;
	}

	.task-title {
		font-size: 1.125rem;
		font-weight: 600;
		color: #1f2937;
	}

	.priority-badge {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		font-weight: 500;
		text-transform: capitalize;
	}

	.priority-urgent {
		background-color: #fef2f2;
		color: #dc2626;
	}

	.priority-high {
		background-color: #fff7ed;
		color: #ea580c;
	}

	.priority-medium {
		background-color: #fefce8;
		color: #ca8a04;
	}

	.priority-low {
		background-color: #f0fdf4;
		color: #16a34a;
	}

	.task-meta {
		display: flex;
		gap: 0.5rem;
		flex-wrap: wrap;
		margin-bottom: 0.75rem;
	}

	.frequency-badge {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		background-color: #dbeafe;
		color: #2563eb;
		font-weight: 500;
	}

	.project-badge {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		font-weight: 500;
	}

	.inactive-badge {
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
		border-radius: 0.25rem;
		background-color: #f3f4f6;
		color: #6b7280;
		font-weight: 500;
	}

	.task-dates {
		display: flex;
		gap: 1rem;
		font-size: 0.875rem;
		color: #6b7280;
		margin-bottom: 0.5rem;
	}

	.date-label {
		font-weight: 500;
	}

	.task-description {
		font-size: 0.875rem;
		color: #6b7280;
		margin-top: 0.5rem;
		line-height: 1.5;
	}

	.task-tags {
		display: flex;
		gap: 0.25rem;
		flex-wrap: wrap;
		margin-top: 0.75rem;
	}

	.tag {
		font-size: 0.75rem;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background-color: #e5e7eb;
		color: #374151;
	}

	.toggle-label {
		display: flex;
		align-items: center;
		cursor: pointer;
	}

	.toggle-checkbox {
		width: 1rem;
		height: 1rem;
		margin-right: 0.5rem;
		accent-color: #2563eb;
	}

	.toggle-text {
		font-size: 0.875rem;
		color: #6b7280;
	}

	/* Dark mode support */
	:global(.dark) .empty-state {
		background-color: #1f2937;
	}

	:global(.dark) .task-title {
		color: #f3f4f6;
	}

	:global(.dark) .tag {
		background-color: #374151;
		color: #d1d5db;
	}

	:global(.dark) .toggle-text {
		color: #9ca3af;
	}
</style>
