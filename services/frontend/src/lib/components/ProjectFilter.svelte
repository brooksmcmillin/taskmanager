<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { projects } from '$lib/stores/projects';

	// Props
	export let selectedProjectId: number | null = null;

	// Subscribe to projects store
	$: projectList = $projects;

	// Event dispatcher
	const dispatch = createEventDispatcher();

	function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const value = target.value;
		const projectId = value === '' ? null : parseInt(value);
		dispatch('change', { projectId });
	}
</script>

<div class="project-filter-container">
	<label for="project-filter" class="project-filter-label">Filter by Project:</label>
	<select
		id="project-filter"
		class="form-select project-filter-select"
		value={selectedProjectId ?? ''}
		on:change={handleChange}
	>
		<option value="">All Projects</option>
		{#each projectList as project}
			<option value={project.id}>
				{project.name}
			</option>
		{/each}
	</select>
</div>
