<script lang="ts">
	import { onMount } from 'svelte';
	import { projects } from '$lib/stores/projects';
	import ProjectModal from '$lib/components/ProjectModal.svelte';
	import type { Project } from '$lib/types';

	let projectModal: ProjectModal;

	onMount(async () => {
		await projects.load();
	});

	function openEditModal(project: Project) {
		projectModal.openEdit(project);
	}

	function openAddModal() {
		projectModal.open();
	}
</script>

<svelte:head>
	<title>Manage Projects</title>
</svelte:head>

<main class="container py-8">
	<h1 class="text-3xl font-bold text-gray-900 mb-8">Manage Projects</h1>

	<ProjectModal bind:this={projectModal} on:save={() => projects.load()} />

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
						<p class="text-xs text-gray-500 mt-2">
							Created: {new Date(project.created_at).toLocaleDateString()}
						</p>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>
