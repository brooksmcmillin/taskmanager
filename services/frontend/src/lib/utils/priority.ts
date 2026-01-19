export type Priority = 'urgent' | 'high' | 'medium' | 'low';

export const PRIORITY_COLORS: Record<Priority, string> = {
	urgent: '#ef4444',
	high: '#f97316',
	medium: '#eab308',
	low: '#22c55e'
} as const;

export function getPriorityColor(priority: string): string {
	return PRIORITY_COLORS[priority as Priority] || '#6b7280';
}
