/**
 * Format a date string for display
 * @param dateStr - ISO date string
 * @returns Formatted date string
 */
export function formatDate(dateStr: string | null): string {
	if (!dateStr) return '';

	const date = new Date(dateStr);
	return date.toLocaleDateString('en-US', {
		year: 'numeric',
		month: 'short',
		day: 'numeric'
	});
}

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
 * @returns Formatted date string for input
 */
export function formatDateForInput(date: Date | string): string {
	const d = typeof date === 'string' ? new Date(date) : date;
	return d.toISOString().split('T')[0];
}

/**
 * Get relative time description (e.g., "2 days ago", "in 3 hours")
 * @param dateStr - ISO date string
 * @returns Relative time string
 */
export function relativeTime(dateStr: string): string {
	const date = new Date(dateStr);
	const now = new Date();
	const diffMs = date.getTime() - now.getTime();
	const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
	const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
	const diffMinutes = Math.floor(diffMs / (1000 * 60));

	if (diffDays > 0) return `in ${diffDays} day${diffDays === 1 ? '' : 's'}`;
	if (diffDays < 0) return `${Math.abs(diffDays)} day${Math.abs(diffDays) === 1 ? '' : 's'} ago`;
	if (diffHours > 0) return `in ${diffHours} hour${diffHours === 1 ? '' : 's'}`;
	if (diffHours < 0)
		return `${Math.abs(diffHours)} hour${Math.abs(diffHours) === 1 ? '' : 's'} ago`;
	if (diffMinutes > 0) return `in ${diffMinutes} minute${diffMinutes === 1 ? '' : 's'}`;
	if (diffMinutes < 0)
		return `${Math.abs(diffMinutes)} minute${Math.abs(diffMinutes) === 1 ? '' : 's'} ago`;

	return 'just now';
}

/**
 * Check if a date is today
 * @param dateStr - ISO date string
 * @returns true if date is today
 */
export function isToday(dateStr: string): boolean {
	const date = new Date(dateStr);
	const today = new Date();

	return (
		date.getDate() === today.getDate() &&
		date.getMonth() === today.getMonth() &&
		date.getFullYear() === today.getFullYear()
	);
}

/**
 * Get start of week (Sunday)
 * @param date - Date object
 * @returns Date object for start of week
 */
export function getStartOfWeek(date: Date): Date {
	const d = new Date(date);
	const day = d.getDay();
	d.setDate(d.getDate() - day);
	d.setHours(0, 0, 0, 0);
	return d;
}
