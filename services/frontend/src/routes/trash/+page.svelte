<script lang="ts">
	import { onMount } from 'svelte';
	import type { Todo } from '$lib/types';

	let tasks: Todo[] = [];
	let searchQuery = '';
	let showClearBtn = false;

	onMount(async () => {
		await loadDeletedTasks();
	});

	function formatDateForDisplay(dateStr: string | null): string {
		if (!dateStr) return '';
		const [year, month, day] = dateStr.split('-').map(Number);
		const date = new Date(year, month - 1, day);
		return date.toLocaleDateString();
	}

	function getPriorityBadgeClass(priority: string): string {
		switch (priority) {
			case 'urgent':
				return 'bg-red-100 text-red-800';
			case 'high':
				return 'bg-orange-100 text-orange-800';
			case 'medium':
				return 'bg-yellow-100 text-yellow-800';
			case 'low':
				return 'bg-green-100 text-green-800';
			default:
				return 'bg-gray-100 text-gray-800';
		}
	}

	async function loadDeletedTasks(query: string = '') {
		try {
			const url = query ? `/api/trash?query=${encodeURIComponent(query)}` : '/api/trash';
			const response = await fetch(url, {
				credentials: 'include'
			});

			if (!response.ok) {
				if (response.status === 401) {
					window.location.href = '/login';
					return;
				}
				throw new Error('Failed to load deleted tasks');
			}

			const data = await response.json();
			tasks = data.data || [];
		} catch (error) {
			console.error('Failed to load deleted tasks:', error);
		}
	}

	async function restoreTask(taskId: number) {
		try {
			const response = await fetch(`/api/trash/${taskId}/restore`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include'
			});

			if (response.ok) {
				// Reload the list after successful restore
				await loadDeletedTasks(searchQuery);
			} else if (response.status === 401) {
				window.location.href = '/login';
			} else {
				const data = await response.json();
				alert(data.detail?.message || data.error?.message || 'Failed to restore task');
			}
		} catch (error) {
			alert('Error: ' + (error as Error).message);
		}
	}

	function handleSearch() {
		const query = searchQuery.trim();
		if (query) {
			loadDeletedTasks(query);
			showClearBtn = true;
		} else {
			loadDeletedTasks();
		}
	}

	function handleClear() {
		searchQuery = '';
		showClearBtn = false;
		loadDeletedTasks();
	}

	function handleKeyPress(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			handleSearch();
		}
	}
</script>

<svelte:head>
	<title>Deleted Tasks</title>
</svelte:head>

<main class="container py-8">
	<h1 class="text-3xl font-bold text-gray-900 mb-8">Deleted Tasks</h1>

	<!-- Search Bar -->
	<div class="max-w-4xl mx-auto mb-6">
		<div class="flex gap-4">
			<input
				type="text"
				bind:value={searchQuery}
				on:keypress={handleKeyPress}
				placeholder="Search deleted tasks..."
				class="form-input flex-1"
			/>
			<button on:click={handleSearch} class="btn btn-primary">Search</button>
			{#if showClearBtn}
				<button on:click={handleClear} class="btn btn-secondary">Clear</button>
			{/if}
		</div>
	</div>

	<!-- Deleted Tasks List -->
	<div class="max-w-4xl mx-auto">
		<div class="space-y-4">
			{#if tasks.length === 0}
				<div class="text-center py-8 text-gray-500">
					<p>No deleted tasks found.</p>
				</div>
			{:else}
				{#each tasks as task}
					<div class="card border-l-4" style="border-left-color: {task.project_color || '#9ca3af'}">
						<div class="flex items-start justify-between gap-4">
							<div class="flex-1 min-w-0">
								<div class="flex items-center gap-2 mb-1">
									<h3 class="font-semibold text-lg text-gray-800 truncate">{task.title}</h3>
									<span class="text-xs px-2 py-1 rounded {getPriorityBadgeClass(task.priority)}">
										{task.priority}
									</span>
								</div>
								<p class="text-gray-600 text-sm mt-1 line-clamp-2">
									{task.description || 'No description'}
								</p>
								<div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 mt-3">
									{#if task.project_name}
										<span>Project: {task.project_name}</span>
									{/if}
									{#if task.due_date}
										<span>Due: {formatDateForDisplay(task.due_date)}</span>
									{/if}
									{#if task.deleted_at}
										<span>Deleted: {formatDateForDisplay(task.deleted_at)}</span>
									{/if}
								</div>
							</div>
							<div class="flex-shrink-0">
								<button
									on:click={() => restoreTask(task.id)}
									class="btn btn-primary btn-sm"
									title="Restore task"
								>
									Restore
								</button>
							</div>
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>
