import { formatDateForInput, getStartOfWeek } from '$lib/utils/dates';

export type DueDateOption = 'all' | 'today' | 'this_week' | 'next_two_weeks' | 'no_due_date';

export interface DueDateFilterValue {
	option: DueDateOption;
	start_date?: string;
	end_date?: string;
	no_due_date?: boolean;
}

export function computeDueDateFilters(option: DueDateOption): Record<string, string | boolean> {
	const today = new Date();
	const todayStr = formatDateForInput(today);

	switch (option) {
		case 'today':
			return { start_date: todayStr, end_date: todayStr };
		case 'this_week': {
			const weekStart = getStartOfWeek(today);
			const weekEnd = new Date(weekStart);
			weekEnd.setDate(weekEnd.getDate() + 6);
			return {
				start_date: formatDateForInput(weekStart),
				end_date: formatDateForInput(weekEnd)
			};
		}
		case 'next_two_weeks': {
			const twoWeeksEnd = new Date(today);
			twoWeeksEnd.setDate(twoWeeksEnd.getDate() + 14);
			return { start_date: todayStr, end_date: formatDateForInput(twoWeeksEnd) };
		}
		case 'no_due_date':
			return { no_due_date: true };
		default:
			return {};
	}
}
