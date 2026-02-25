import type { DeadlineType } from '$lib/types';

export const DEADLINE_TYPE_CONFIG: Record<DeadlineType, { label: string; color: string; description: string }> = {
	flexible: {
		label: 'Flexible',
		color: '#6b7280',
		description: 'Reschedule freely'
	},
	preferred: {
		label: 'Preferred',
		color: '#3b82f6',
		description: 'Soft target date'
	},
	firm: {
		label: 'Firm',
		color: '#f97316',
		description: 'Avoid moving'
	},
	hard: {
		label: 'Hard',
		color: '#ef4444',
		description: 'Never reschedule'
	}
} as const;

export function getDeadlineTypeLabel(type: string): string {
	return DEADLINE_TYPE_CONFIG[type as DeadlineType]?.label || type;
}

export function getDeadlineTypeColor(type: string): string {
	return DEADLINE_TYPE_CONFIG[type as DeadlineType]?.color || '#6b7280';
}

export function getDeadlineTypeDescription(type: string): string {
	return DEADLINE_TYPE_CONFIG[type as DeadlineType]?.description || '';
}
