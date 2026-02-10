<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { formatDateForInput, getStartOfWeek } from '$lib/utils/dates';

	export type DueDateOption = 'all' | 'today' | 'this_week' | 'next_two_weeks' | 'no_due_date';

	export interface DueDateFilterValue {
		option: DueDateOption;
		start_date?: string;
		end_date?: string;
		no_due_date?: boolean;
	}

	export let selected: DueDateOption = 'all';

	const dispatch = createEventDispatcher<{ change: DueDateFilterValue }>();

	function getFilterValue(option: DueDateOption): DueDateFilterValue {
		const today = new Date();
		const todayStr = formatDateForInput(today);

		switch (option) {
			case 'today':
				return { option, start_date: todayStr, end_date: todayStr };
			case 'this_week': {
				const weekStart = getStartOfWeek(today);
				const weekEnd = new Date(weekStart);
				weekEnd.setDate(weekEnd.getDate() + 6);
				return {
					option,
					start_date: formatDateForInput(weekStart),
					end_date: formatDateForInput(weekEnd)
				};
			}
			case 'next_two_weeks': {
				const twoWeeksEnd = new Date(today);
				twoWeeksEnd.setDate(twoWeeksEnd.getDate() + 14);
				return {
					option,
					start_date: todayStr,
					end_date: formatDateForInput(twoWeeksEnd)
				};
			}
			case 'no_due_date':
				return { option, no_due_date: true };
			default:
				return { option: 'all' };
		}
	}

	function handleChange(event: Event) {
		const target = event.target as HTMLSelectElement;
		const option = target.value as DueDateOption;
		selected = option;
		dispatch('change', getFilterValue(option));
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
