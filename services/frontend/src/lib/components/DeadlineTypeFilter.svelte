<script lang="ts">
	import type { DeadlineType } from '$lib/types';
	import { DEADLINE_TYPE_CONFIG } from '$lib/utils/deadline';

	let {
		selected = null,
		onchange
	}: {
		selected: DeadlineType | null;
		onchange: (detail: { deadlineType: DeadlineType | null }) => void;
	} = $props();

	function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const value = target.value;
		const deadlineType = value === '' ? null : (value as DeadlineType);
		onchange({ deadlineType });
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
		onchange={handleChange}
	>
		<option value="">All Types</option>
		{#each Object.entries(DEADLINE_TYPE_CONFIG) as [value, config]}
			<option {value}>
				{config.label} - {config.description}
			</option>
		{/each}
	</select>
</div>
