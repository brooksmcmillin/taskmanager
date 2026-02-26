<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import type { DeadlineType } from '$lib/types';
	import { DEADLINE_TYPE_CONFIG } from '$lib/utils/deadline';

	export let selected: DeadlineType | null = null;

	const dispatch = createEventDispatcher();

	function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const value = target.value;
		const deadlineType = value === '' ? null : (value as DeadlineType);
		dispatch('change', { deadlineType });
	}
</script>

<div class="deadline-type-filter-container">
	<label for="deadline-type-filter" class="deadline-type-filter-label"
		>Filter by Deadline Type:</label
	>
	<select
		id="deadline-type-filter"
		class="form-select deadline-type-filter-select"
		value={selected ?? ''}
		on:change={handleChange}
	>
		<option value="">All Types</option>
		{#each Object.entries(DEADLINE_TYPE_CONFIG) as [value, config]}
			<option {value}>
				{config.label} - {config.description}
			</option>
		{/each}
	</select>
</div>
