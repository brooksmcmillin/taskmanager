/**
 * Format a date string for display using locale default
 * @param dateStr - Date string in YYYY-MM-DD format or null
 * @param fallback - Optional fallback string when date is null
 * @returns Formatted date string or fallback
 */
export function formatDateDisplay(dateStr: string | null, fallback = ''): string {
	if (!dateStr) return fallback;
	const [year, month, day] = dateStr.split('-').map(Number);
	const date = new Date(year, month - 1, day);
	return date.toLocaleDateString();
}

/**
 * Format a date for input fields (YYYY-MM-DD)
 * @param date - Date object or ISO string
 * @returns Formatted date string for input in local timezone
 */
export function formatDateForInput(date: Date | string): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	// Use local timezone instead of UTC
	const year = d.getFullYear();
	const month = String(d.getMonth() + 1).padStart(2, '0');
	const day = String(d.getDate()).padStart(2, '0');
	return `${year}-${month}-${day}`;
}

/**
 * Check if a date is today
 * @param dateStr - Date string (YYYY-MM-DD format or ISO string)
 * @returns true if date is today
 */
export function isToday(dateStr: string): boolean {
	// Get today's date in local time
	const today = new Date();
	const todayStr = formatDateForInput(today);

	// If input is YYYY-MM-DD format, compare directly
	if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
		return dateStr === todayStr;
	}

	// Otherwise parse and compare (for backward compatibility with ISO strings)
	const date = new Date(dateStr);
	return (
		date.getDate() === today.getDate() &&
		date.getMonth() === today.getMonth() &&
		date.getFullYear() === today.getFullYear()
	);
}

/**
 * Get start of week (Monday)
 * @param date - Date object
 * @returns Date object for start of week (Monday)
 */
export function getStartOfWeek(date: Date): Date {
	const d = new Date(date);
	const day = d.getDay();
	// Convert Sunday (0) to 7, so Monday becomes day 1
	const daysFromMonday = (day + 6) % 7;
	d.setDate(d.getDate() - daysFromMonday);
	d.setHours(0, 0, 0, 0);
	return d;
}

/**
 * Parse a date string as local midnight (not UTC)
 * @param dateStr - Date string in YYYY-MM-DD format
 * @returns Date object at local midnight
 */
function localMidnight(dateStr: string): Date {
	// Parse YYYY-MM-DD as local midnight (not UTC) so date comparisons
	// reflect the user's timezone. Do NOT use new Date(dateStr) or
	// append 'T00:00:00Z' — both interpret as UTC which shifts the
	// date for users west of Greenwich.
	const [y, m, d] = dateStr.split('-').map(Number);
	return new Date(y, m - 1, d);
}

/**
 * Format a due date for display (e.g., "today", "tomorrow", "3d ago", or short date)
 * @param dateStr - Date string in YYYY-MM-DD format or null
 * @returns Formatted date string
 */
export function formatDueDate(dateStr: string | null): string {
	if (!dateStr) return '';
	const due = localMidnight(dateStr);
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const diff = Math.floor((due.getTime() - today.getTime()) / 86400000);
	if (diff < 0) return `${Math.abs(diff)}d overdue`;
	if (diff === 0) return 'today';
	if (diff === 1) return 'tomorrow';
	return due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * Format a timestamp as relative time (e.g., "5m ago", "2h ago", "Mar 5")
 * @param dateStr - ISO timestamp string or null
 * @returns Relative time string
 */
export function timeAgo(dateStr: string | null): string {
	if (!dateStr) return '';
	const now = new Date();
	const then = new Date(dateStr);
	const diffMs = now.getTime() - then.getTime();
	const mins = Math.floor(diffMs / 60000);
	if (mins < 1) return 'just now';
	if (mins < 60) return `${mins}m ago`;
	const hours = Math.floor(mins / 60);
	if (hours < 24) return `${hours}h ago`;
	const days = Math.floor(hours / 24);
	if (days < 7) return `${days}d ago`;
	return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
