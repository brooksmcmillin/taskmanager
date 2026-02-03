<script lang="ts">
	import { onMount } from 'svelte';
	import { projects } from '$lib/stores/projects';
	import ProjectModal from '$lib/components/ProjectModal.svelte';
	import type { Project } from '$lib/types';

	let projectModal: ProjectModal;

	onMount(async () => {
		await projects.load({ includeStats: true });
	});

	function openEditModal(project: Project) {
		projectModal.openEdit(project);
	}

	function openAddModal() {
		projectModal.open();
	}

	function formatHours(hours: number | null | undefined): string {
		if (hours === null || hours === undefined) return '-';
		return `${hours.toFixed(1)}h`;
	}
</script>

<svelte:head>
	<title>Manage Projects</title>
</svelte:head>

<main class="container py-8">
	<ProjectModal bind:this={projectModal} on:save={() => projects.load({ includeStats: true })} />

	<!-- Existing Projects -->
	<div class="max-w-4xl mx-auto">
		<h2 class="text-xl font-semibold mb-4">Your Projects</h2>
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
			{#if $projects.length === 0}
				<p class="text-gray-500">No projects yet. Create your first project!</p>
			{:else}
				{#each $projects as project}
					<div class="card border-l-4 relative" style="border-left-color: {project.color}">
						<div class="flex justify-between items-start mb-2">
							<h3 class="font-semibold text-lg text-gray-800">{project.name}</h3>
							<button on:click={() => openEditModal(project)} class="btn btn-secondary btn-sm">
								Edit
							</button>
						</div>
						<p class="text-gray-600 text-sm mt-1">{project.description || 'No description'}</p>

						{#if project.stats && project.stats.total_tasks > 0}
							<!-- Progress bar -->
							<div class="mt-3">
								<div class="flex justify-between text-xs text-gray-500 mb-1">
									<span>{project.stats.completed_tasks} / {project.stats.total_tasks} tasks</span>
									<span>{project.stats.completion_percentage}%</span>
								</div>
								<div class="w-full bg-gray-200 rounded-full h-2">
									<div
										class="h-2 rounded-full transition-all duration-300"
										class:bg-green-500={project.stats.completion_percentage === 100}
										class:bg-blue-500={project.stats.completion_percentage < 100}
										style="width: {project.stats.completion_percentage}%"
									></div>
								</div>
							</div>

							<!-- Stats grid -->
							<div class="mt-3 grid grid-cols-3 gap-2 text-xs">
								<div class="text-center p-1 bg-gray-50 rounded">
									<div class="font-medium text-gray-700">{project.stats.pending_tasks}</div>
									<div class="text-gray-500">Pending</div>
								</div>
								<div class="text-center p-1 bg-gray-50 rounded">
									<div class="font-medium text-gray-700">{project.stats.in_progress_tasks}</div>
									<div class="text-gray-500">In Progress</div>
								</div>
								{#if project.stats.overdue_tasks > 0}
									<div class="text-center p-1 bg-red-50 rounded">
										<div class="font-medium text-red-600">{project.stats.overdue_tasks}</div>
										<div class="text-red-500">Overdue</div>
									</div>
								{:else}
									<div class="text-center p-1 bg-gray-50 rounded">
										<div class="font-medium text-gray-700">{project.stats.completed_tasks}</div>
										<div class="text-gray-500">Done</div>
									</div>
								{/if}
							</div>

							<!-- Hours tracking -->
							{#if project.stats.total_estimated_hours}
								<div class="mt-2 text-xs text-gray-500 flex justify-between">
									<span>Est: {formatHours(project.stats.total_estimated_hours)}</span>
									{#if project.stats.total_actual_hours}
										<span>Actual: {formatHours(project.stats.total_actual_hours)}</span>
									{/if}
								</div>
							{/if}
						{:else}
							<p class="text-xs text-gray-400 mt-3 italic">No tasks yet</p>
						{/if}

						<p class="text-xs text-gray-500 mt-2">
							Created: {new Date(project.created_at).toLocaleDateString()}
						</p>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>
