<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { computeDueDateFilters } from '$lib/utils/dueDateFilter';
	import type { DueDateOption, DueDateFilterValue } from '$lib/utils/dueDateFilter';

	export let selected: DueDateOption = 'all';

	const dispatch = createEventDispatcher<{ change: DueDateFilterValue }>();

	function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const option = target.value as DueDateOption;
		selected = option;
		dispatch('change', { option, ...computeDueDateFilters(option) });
	}
</script>

<div class="due-date-filter-container">
	<label for="due-date-filter" class="due-date-filter-label">Due Date:</label>
	<select
		id="due-date-filter"
		class="form-select due-date-filter-select"
		value={selected}
		on:change={handleChange}
	>
		<option value="all">All Dates</option>
		<option value="today">Today</option>
		<option value="this_week">This Week</option>
		<option value="next_two_weeks">Next Two Weeks</option>
		<option value="no_due_date">No Due Date</option>
	</select>
</div>
