import type { ActionType, AgentStatus, AutonomyTier, TimeHorizon } from '$lib/types';

export const ACTION_TYPE_CONFIG: Record<
	ActionType,
	{ label: string; color: string; bgColor: string }
> = {
	research: { label: 'Research', color: '#3b82f6', bgColor: '#eff6ff' },
	code: { label: 'Code', color: '#8b5cf6', bgColor: '#f5f3ff' },
	email: { label: 'Email', color: '#06b6d4', bgColor: '#ecfeff' },
	document: { label: 'Document', color: '#6366f1', bgColor: '#eef2ff' },
	purchase: { label: 'Purchase', color: '#f59e0b', bgColor: '#fffbeb' },
	schedule: { label: 'Schedule', color: '#10b981', bgColor: '#ecfdf5' },
	call: { label: 'Call', color: '#14b8a6', bgColor: '#f0fdfa' },
	errand: { label: 'Errand', color: '#f97316', bgColor: '#fff7ed' },
	manual: { label: 'Manual', color: '#78716c', bgColor: '#f5f5f4' },
	review: { label: 'Review', color: '#a855f7', bgColor: '#faf5ff' },
	data_entry: { label: 'Data Entry', color: '#64748b', bgColor: '#f8fafc' },
	other: { label: 'Other', color: '#6b7280', bgColor: '#f9fafb' }
} as const;

export const AGENT_STATUS_CONFIG: Record<
	AgentStatus,
	{ label: string; color: string; bgColor: string }
> = {
	pending_review: { label: 'Pending Review', color: '#f59e0b', bgColor: '#fffbeb' },
	in_progress: { label: 'In Progress', color: '#3b82f6', bgColor: '#eff6ff' },
	completed: { label: 'Completed', color: '#22c55e', bgColor: '#f0fdf4' },
	blocked: { label: 'Blocked', color: '#ef4444', bgColor: '#fef2f2' },
	needs_human: { label: 'Needs Human', color: '#f97316', bgColor: '#fff7ed' }
} as const;

export const AUTONOMY_TIER_CONFIG: Record<
	AutonomyTier,
	{ label: string; color: string; bgColor: string; description: string }
> = {
	1: {
		label: 'Tier 1 - Autonomous',
		color: '#22c55e',
		bgColor: '#f0fdf4',
		description: 'Fully autonomous (read-only, no side effects)'
	},
	2: {
		label: 'Tier 2 - Propose & Execute',
		color: '#3b82f6',
		bgColor: '#eff6ff',
		description: 'Propose & execute (async notification, can be reverted)'
	},
	3: {
		label: 'Tier 3 - Propose & Wait',
		color: '#f59e0b',
		bgColor: '#fffbeb',
		description: 'Propose & wait (explicit approval before execution)'
	},
	4: {
		label: 'Tier 4 - Never Autonomous',
		color: '#ef4444',
		bgColor: '#fef2f2',
		description: 'Never autonomous (always human-executed)'
	}
} as const;

export const TIME_HORIZON_CONFIG: Record<
	TimeHorizon,
	{ label: string; color: string; bgColor: string }
> = {
	today: { label: 'Today', color: '#ef4444', bgColor: '#fef2f2' },
	this_week: { label: 'This Week', color: '#f97316', bgColor: '#fff7ed' },
	next_week: { label: 'Next Week', color: '#f59e0b', bgColor: '#fffbeb' },
	this_month: { label: 'This Month', color: '#eab308', bgColor: '#fefce8' },
	next_month: { label: 'Next Month', color: '#84cc16', bgColor: '#f7fee7' },
	this_quarter: { label: 'This Quarter', color: '#22c55e', bgColor: '#f0fdf4' },
	next_quarter: { label: 'Next Quarter', color: '#10b981', bgColor: '#ecfdf5' },
	this_year: { label: 'This Year', color: '#06b6d4', bgColor: '#ecfeff' },
	next_year: { label: 'Next Year', color: '#3b82f6', bgColor: '#eff6ff' },
	someday: { label: 'Someday', color: '#6b7280', bgColor: '#f9fafb' }
} as const;

export function getActionTypeLabel(type: string): string {
	return ACTION_TYPE_CONFIG[type as ActionType]?.label || type;
}

export function getActionTypeColor(type: string): string {
	return ACTION_TYPE_CONFIG[type as ActionType]?.color || '#6b7280';
}

export function getActionTypeBgColor(type: string): string {
	return ACTION_TYPE_CONFIG[type as ActionType]?.bgColor || '#f9fafb';
}

export function getAgentStatusLabel(status: string): string {
	return AGENT_STATUS_CONFIG[status as AgentStatus]?.label || status;
}

export function getAgentStatusColor(status: string): string {
	return AGENT_STATUS_CONFIG[status as AgentStatus]?.color || '#6b7280';
}

export function getAgentStatusBgColor(status: string): string {
	return AGENT_STATUS_CONFIG[status as AgentStatus]?.bgColor || '#f9fafb';
}

export function getAutonomyTierLabel(tier: number): string {
	return AUTONOMY_TIER_CONFIG[tier as AutonomyTier]?.label || `Tier ${tier}`;
}

export function getAutonomyTierColor(tier: number): string {
	return AUTONOMY_TIER_CONFIG[tier as AutonomyTier]?.color || '#6b7280';
}

export function getAutonomyTierBgColor(tier: number): string {
	return AUTONOMY_TIER_CONFIG[tier as AutonomyTier]?.bgColor || '#f9fafb';
}

export function getAutonomyTierDescription(tier: number): string {
	return AUTONOMY_TIER_CONFIG[tier as AutonomyTier]?.description || '';
}

export function getTimeHorizonLabel(horizon: string): string {
	return TIME_HORIZON_CONFIG[horizon as TimeHorizon]?.label || horizon;
}

export function getTimeHorizonColor(horizon: string): string {
	return TIME_HORIZON_CONFIG[horizon as TimeHorizon]?.color || '#6b7280';
}

export function getTimeHorizonBgColor(horizon: string): string {
	return TIME_HORIZON_CONFIG[horizon as TimeHorizon]?.bgColor || '#f9fafb';
}
