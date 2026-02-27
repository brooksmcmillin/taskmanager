<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { dndzone } from 'svelte-dnd-action';
	import type { DndEvent } from 'svelte-dnd-action';
	import { todos, pendingTodos } from '$lib/stores/todos';
	import { hexTo50Shade, contrastText } from '$lib/utils/colors';
	import { getDeadlineTypeColor, getDeadlineTypeLabel } from '$lib/utils/deadline';
	import { getStartOfWeek, formatDateForInput, isToday } from '$lib/utils/dates';
	import { logger } from '$lib/utils/logger';
	import { goto } from '$app/navigation';
	import type { Todo, TodoFilters, Subtask } from '$lib/types';

	export let filters: TodoFilters = {};

	const DEFAULT_PROJECT_COLOR = '#6b7280';
	const MAX_VISIBLE_TASKS = 3;
	const dispatch = createEventDispatcher<{ editTodo: Todo }>();

	// Start from the previous week's Monday to show past/current/next week
	let currentWeekStart = (() => {
		const thisWeekMonday = getStartOfWeek(new Date());
		thisWeekMonday.setDate(thisWeekMonday.getDate() - 7);
		return thisWeekMonday;
	})();

	// Unified item type for the dndzone - represents both parent tasks and subtasks
	interface CalendarItem {
		id: number;
		title: string;
		priority: 'low' | 'medium' | 'high' | 'urgent';
		due_date: string | null;
		isSubtask: boolean;
		// Parent task fields (present when isSubtask is false)
		project_color?: string | null;
		deadline_type?: string | null;
		subtasks?: Subtask[];
		// Subtask fields (present when isSubtask is true)
		parentId?: number;
		parentTitle?: string;
		parentColor?: string | null;
	}

	let itemsByDate: Record<string, CalendarItem[]> = {};
	// Track drag operation state
	let draggedItemId: number | null = null;
	let originalDate: string | null = null;
	let isDragging = false;
	// Per-day expand state for overflow
	let expandedDays: Record<string, boolean> = {};
	// Mobile: selected day for detail view
	let selectedDay: string = formatDateForInput(new Date());

	interface Day {
		date: Date;
		dateStr: string;
		isToday: boolean;
	}

	$: days = generateDays(currentWeekStart, 21);

	// Keep selectedDay within visible range when navigating weeks
	$: {
		const dayStrs = days.map((d) => d.dateStr);
		if (!dayStrs.includes(selectedDay)) {
			const todayDay = days.find((d) => d.isToday);
			selectedDay = todayDay ? todayDay.dateStr : (days[7]?.dateStr ?? days[0]?.dateStr);
		}
	}

	// Mobile detail view: derive parent tasks and subtasks from itemsByDate
	$: selectedDayItems = itemsByDate[selectedDay] || [];
	$: selectedDayTasks = selectedDayItems.filter((i) => !i.isSubtask);
	$: selectedDaySubtasks = selectedDayItems.filter((i) => i.isSubtask);

	function formatDayHeader(dateStr: string): string {
		const [year, month, day] = dateStr.split('-').map(Number);
		const date = new Date(year, month - 1, day);
		const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
		const monthNames = [
			'Jan',
			'Feb',
			'Mar',
			'Apr',
			'May',
			'Jun',
			'Jul',
			'Aug',
			'Sep',
			'Oct',
			'Nov',
			'Dec'
		];
		return `${dayNames[date.getDay()]}, ${monthNames[date.getMonth()]} ${date.getDate()}`;
	}

	function generateDays(start: Date, count: number): Day[] {
		return Array.from({ length: count }, (_, i) => {
			const date = new Date(start);
			date.setDate(date.getDate() + i);
			const dateStr = formatDateForInput(date);
			return {
				date,
				dateStr,
				isToday: isToday(dateStr)
			};
		});
	}

	function groupTodosByDate(todosList: Todo[]): Record<string, CalendarItem[]> {
		const grouped: Record<string, CalendarItem[]> = {};

		// Initialize arrays for all visible dates
		for (const day of days) {
			grouped[day.dateStr] = [];
		}

		// Add todos and their subtasks to their respective dates
		todosList.forEach((todo) => {
			if (todo.due_date) {
				const dateStr = todo.due_date.split('T')[0];
				if (!grouped[dateStr]) grouped[dateStr] = [];
				grouped[dateStr].push({
					id: todo.id,
					title: todo.title,
					priority: todo.priority,
					due_date: todo.due_date,
					isSubtask: false,
					project_color: todo.project_color,
					deadline_type: todo.deadline_type,
					subtasks: todo.subtasks
				});
			}

			// Extract pending subtasks as separate calendar items
			const parentDueDate = todo.due_date ? todo.due_date.split('T')[0] : null;
			(todo.subtasks || []).forEach((subtask) => {
				if (subtask.status === 'completed') return;
				const dateStr = subtask.due_date ? subtask.due_date.split('T')[0] : parentDueDate;
				if (!dateStr) return;
				if (!grouped[dateStr]) grouped[dateStr] = [];
				grouped[dateStr].push({
					id: subtask.id,
					title: subtask.title,
					priority: subtask.priority,
					due_date: dateStr,
					isSubtask: true,
					parentId: todo.id,
					parentTitle: todo.title,
					parentColor: todo.project_color || null
				});
			});
		});

		return grouped;
	}

	function handleConsider(dateStr: string, event: CustomEvent<DndEvent<CalendarItem>>) {
		// Track what's being dragged when drag starts
		if (event.detail.info.trigger === 'dragStarted') {
			isDragging = true;
			const draggedId = event.detail.info.id;
			// Convert draggedId to number for comparison with item.id
			const draggedIdNum = typeof draggedId === 'string' ? parseInt(draggedId, 10) : draggedId;
			// Find the item being dragged across all dates
			for (const [, items] of Object.entries(itemsByDate)) {
				if (items) {
					const item = items.find((i) => i && i.id === draggedIdNum);
					if (item && item.due_date) {
						draggedItemId = draggedIdNum;
						originalDate = item.due_date.split('T')[0];
						break;
					}
				}
			}
		}

		// Update local state - svelte-dnd-action gives us the new items array for this date
		// This is what the date WILL look like if the drag completes
		itemsByDate = { ...itemsByDate, [dateStr]: event.detail.items as CalendarItem[] };
	}

	async function handleFinalize(dateStr: string, event: CustomEvent<DndEvent<CalendarItem>>) {
		// Update local state first - this is what svelte-dnd-action expects
		itemsByDate = { ...itemsByDate, [dateStr]: event.detail.items as CalendarItem[] };

		// Only make API call if item was actually moved to a different date
		if (draggedItemId !== null && originalDate !== null && originalDate !== dateStr) {
			const itemId = draggedItemId;

			try {
				// updateTodo sends PUT /api/todos/{id} - works for both parent tasks and subtasks
				await todos.updateTodo(itemId, { due_date: dateStr });

				// Reload to ensure subtask changes are correctly reflected in the store
				// (subtasks are nested inside parent todos, so updateTodo's local store
				// update won't find them at the top level)
				await todos.load({ ...filters, status: 'pending' });
				const currentTodos = get(pendingTodos);
				itemsByDate = groupTodosByDate(currentTodos);

				// Clear drag tracking AFTER manual rebuild to prevent subscription race
				isDragging = false;
				draggedItemId = null;
				originalDate = null;
			} catch (error) {
				logger.error('Failed to update todo date:', error);
				// Reload all todos to revert the change
				await todos.load({ ...filters, status: 'pending' });
				const currentTodos = get(pendingTodos);
				itemsByDate = groupTodosByDate(currentTodos);

				// Clear drag tracking after error recovery
				isDragging = false;
				draggedItemId = null;
				originalDate = null;
			}
		} else {
			// Item was dropped in same column or drag cancelled
			// Just clear drag state - local state already updated above
			isDragging = false;
			draggedItemId = null;
			originalDate = null;
		}
	}

	function prevWeek() {
		const newDate = new Date(currentWeekStart);
		newDate.setDate(newDate.getDate() - 7);
		currentWeekStart = newDate;
		expandedDays = {};
	}

	function nextWeek() {
		const newDate = new Date(currentWeekStart);
		newDate.setDate(newDate.getDate() + 7);
		currentWeekStart = newDate;
		expandedDays = {};
	}

	function goToToday() {
		const thisWeekMonday = getStartOfWeek(new Date());
		thisWeekMonday.setDate(thisWeekMonday.getDate() - 7);
		currentWeekStart = thisWeekMonday;
		selectedDay = formatDateForInput(new Date());
		expandedDays = {};
	}

	function handleItemClick(item: CalendarItem) {
		if (isDragging) return;
		if (item.isSubtask) {
			goto(`/task/${item.id}`);
		} else {
			// Look up the full Todo object from the store for the detail panel
			const allTodos = get(pendingTodos);
			const todo = allTodos.find((t) => t.id === item.id);
			if (todo) {
				dispatch('editTodo', todo);
			}
		}
	}

	function dayHasOverflow(dateStr: string): boolean {
		const items = itemsByDate[dateStr] || [];
		return items.length > MAX_VISIBLE_TASKS;
	}

	function toggleDayExpand(dateStr: string) {
		expandedDays = { ...expandedDays, [dateStr]: !expandedDays[dateStr] };
	}

	// Reference itemsByDate directly so Svelte tracks it as a dependency
	$: hasAnyOverflow = itemsByDate && days.some(({ dateStr }) => dayHasOverflow(dateStr));

	$: allExpanded =
		hasAnyOverflow &&
		itemsByDate &&
		days.every(({ dateStr }) => !dayHasOverflow(dateStr) || expandedDays[dateStr]);

	function toggleExpandAll() {
		const expanding = !allExpanded;
		const newState: Record<string, boolean> = {};
		for (const { dateStr } of days) {
			if (dayHasOverflow(dateStr)) {
				newState[dateStr] = expanding;
			}
		}
		expandedDays = newState;
	}

	onMount(() => {
		// Subscribe to pendingTodos and rebuild the calendar whenever it changes
		// But don't update during drag operations to avoid interfering with the drag
		const unsubscribe = pendingTodos.subscribe((value) => {
			if (!isDragging) {
				itemsByDate = groupTodosByDate(value);
			}
		});

		// Load initial todos
		todos.load({ ...filters, status: 'pending' });

		return unsubscribe;
	});
</script>

<div class="card" id="drag-drop-calendar">
	<div class="calendar-top-nav">
		<h2 class="text-xl font-semibold">Task Calendar</h2>
		<div class="calendar-nav-buttons">
			<button class="btn btn-secondary btn-sm" on:click={prevWeek}>← Previous</button>
			<button class="btn btn-secondary btn-sm" on:click={goToToday}>Today</button>
			<button class="btn btn-secondary btn-sm" on:click={nextWeek}>Next →</button>
			{#if hasAnyOverflow}
				<button class="btn btn-secondary btn-sm expand-all-btn" on:click={toggleExpandAll}>
					{allExpanded ? 'Collapse All' : 'Expand All'}
				</button>
			{/if}
		</div>
	</div>

	<!-- Mobile: Week strip + day detail -->
	<div class="mobile-calendar">
		<div class="week-strip-headers">
			{#each ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as dayName}
				<div class="week-strip-header">{dayName}</div>
			{/each}
		</div>
		<div class="week-strip-grid">
			{#each days as { date, dateStr, isToday: isTodayDay }}
				{@const taskCount = (itemsByDate[dateStr] || []).length}
				<button
					class="day-pill"
					class:selected={selectedDay === dateStr}
					class:today={isTodayDay}
					on:click={() => (selectedDay = dateStr)}
				>
					<span class="day-pill-date">{date.getDate()}</span>
					{#if taskCount > 0}
						<span class="task-dot" class:task-dot-selected={selectedDay === dateStr}></span>
					{/if}
				</button>
			{/each}
		</div>

		<div class="day-detail">
			<div class="day-detail-header">
				<span class="day-detail-title">{formatDayHeader(selectedDay)}</span>
				<span class="day-detail-count">
					{selectedDayTasks.length + selectedDaySubtasks.length} tasks
				</span>
			</div>
			{#if selectedDayTasks.length === 0 && selectedDaySubtasks.length === 0}
				<div class="day-detail-empty">No tasks scheduled</div>
			{:else}
				<div class="day-detail-tasks">
					{#each selectedDayTasks as item (item.id)}
						{@const subtasks = item.subtasks || []}
						{@const completedSubtaskCount = subtasks.filter((s) => s.status === 'completed').length}
						<div
							class="mobile-task-card"
							style="border-left: 4px solid {item.project_color ||
								DEFAULT_PROJECT_COLOR}; background-color: {hexTo50Shade(
								item.project_color || DEFAULT_PROJECT_COLOR
							)}"
							on:click={() => handleItemClick(item)}
							role="button"
							tabindex="0"
							on:keydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') handleItemClick(item);
							}}
						>
							<div class="mobile-task-title">{item.title}</div>
							<div class="mobile-task-meta">
								<span class="mobile-task-priority">{item.priority}</span>
								{#if item.deadline_type && item.deadline_type !== 'preferred'}
									<span
										class="mobile-task-deadline"
										style="color: {getDeadlineTypeColor(item.deadline_type)}"
									>
										{getDeadlineTypeLabel(item.deadline_type)}
									</span>
								{/if}
								{#if subtasks.length > 0}
									<span class="mobile-task-subtasks">
										{completedSubtaskCount}/{subtasks.length}
									</span>
								{/if}
							</div>
						</div>
					{/each}
					{#each selectedDaySubtasks as subtask (subtask.id)}
						<div
							class="mobile-task-card mobile-subtask-card"
							style="border-left: 4px solid {subtask.parentColor ||
								DEFAULT_PROJECT_COLOR}; background-color: {hexTo50Shade(
								subtask.parentColor || DEFAULT_PROJECT_COLOR
							)}"
							on:click={() => goto(`/task/${subtask.id}`)}
							role="button"
							tabindex="0"
							on:keydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') goto(`/task/${subtask.id}`);
							}}
						>
							<div
								class="mobile-subtask-parent"
								style="background-color: {subtask.parentColor ||
									DEFAULT_PROJECT_COLOR}; color: {contrastText(
									subtask.parentColor || DEFAULT_PROJECT_COLOR
								)}"
							>
								#{subtask.parentId}
								{subtask.parentTitle}
							</div>
							<div class="mobile-task-title">{subtask.title}</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	<!-- Desktop: Grid view -->
	<div id="calendar-container" class="desktop-calendar">
		<div class="calendar-headers">
			{#each [{ full: 'Monday', short: 'Mon' }, { full: 'Tuesday', short: 'Tue' }, { full: 'Wednesday', short: 'Wed' }, { full: 'Thursday', short: 'Thu' }, { full: 'Friday', short: 'Fri' }, { full: 'Saturday', short: 'Sat' }, { full: 'Sunday', short: 'Sun' }] as day}
				<div class="calendar-header-day">
					<span class="day-full">{day.full}</span>
					<span class="day-short">{day.short}</span>
				</div>
			{/each}
		</div>

		<div id="calendar-grid">
			{#each days as { date, dateStr, isToday: isTodayDay }}
				{@const allItems = itemsByDate[dateStr] || []}
				{@const isExpanded = expandedDays[dateStr] || false}
				{@const overflow = isExpanded ? 0 : Math.max(0, allItems.length - MAX_VISIBLE_TASKS)}
				<div class="calendar-day" class:today={isTodayDay} data-date={dateStr}>
					<div class="calendar-date">
						{date.getMonth() + 1}/{date.getDate()}
					</div>
					<div
						class="tasks-container"
						use:dndzone={{
							items: itemsByDate[dateStr] || [],
							dropTargetStyle: { outline: '2px dashed #3b82f6' },
							type: 'todo',
							flipDurationMs: 200
						}}
						on:consider={(e) => handleConsider(dateStr, e)}
						on:finalize={(e) => handleFinalize(dateStr, e)}
					>
						{#each allItems as item, idx (item.id)}
							{@const isHidden = !isExpanded && idx >= MAX_VISIBLE_TASKS}
							{#if item.isSubtask}
								<div
									class="calendar-task calendar-subtask-item {item.priority}-priority"
									class:calendar-task-hidden={isHidden}
									style="background-color: {hexTo50Shade(
										item.parentColor || DEFAULT_PROJECT_COLOR
									)}; border-left: 4px solid {item.parentColor || DEFAULT_PROJECT_COLOR}"
									on:click={() => handleItemClick(item)}
									role="button"
									tabindex="0"
									on:keydown={(e) => {
										if (e.key === 'Enter' || e.key === ' ') handleItemClick(item);
									}}
								>
									<div
										class="calendar-subtask-parent"
										style="background-color: {item.parentColor ||
											DEFAULT_PROJECT_COLOR}; color: {contrastText(
											item.parentColor || DEFAULT_PROJECT_COLOR
										)}"
									>
										#{item.parentId}
										{item.parentTitle}
									</div>
									<div class="task-title">{item.title}</div>
								</div>
							{:else}
								{@const subtasks = item.subtasks || []}
								{@const completedSubtaskCount = subtasks.filter(
									(s) => s.status === 'completed'
								).length}
								<div
									class="calendar-task {item.priority}-priority"
									class:calendar-task-hidden={isHidden}
									style="background-color: {hexTo50Shade(
										item.project_color || DEFAULT_PROJECT_COLOR
									)}; border-left: 4px solid {item.project_color || DEFAULT_PROJECT_COLOR}"
									on:click={() => handleItemClick(item)}
									role="button"
									tabindex="0"
									on:keydown={(e) => {
										if (e.key === 'Enter' || e.key === ' ') handleItemClick(item);
									}}
								>
									<div class="task-title">{item.title}</div>
									{#if (item.deadline_type && item.deadline_type !== 'preferred') || subtasks.length > 0}
										<div class="calendar-task-meta">
											{#if item.deadline_type && item.deadline_type !== 'preferred'}
												<span
													class="calendar-deadline-type"
													style="color: {getDeadlineTypeColor(item.deadline_type)}"
													title="{getDeadlineTypeLabel(item.deadline_type)} deadline"
												>
													{getDeadlineTypeLabel(item.deadline_type)}
												</span>
											{/if}
											{#if subtasks.length > 0}
												<span class="calendar-subtask-count"
													>{completedSubtaskCount}/{subtasks.length}</span
												>
											{/if}
										</div>
									{/if}
								</div>
							{/if}
						{/each}
					</div>
					{#if overflow > 0}
						<button class="calendar-overflow" on:click={() => toggleDayExpand(dateStr)}>
							+{overflow} more
						</button>
					{:else if isExpanded && allItems.length > MAX_VISIBLE_TASKS}
						<button class="calendar-overflow" on:click={() => toggleDayExpand(dateStr)}>
							Show less
						</button>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>

<style>
	.calendar-task-hidden {
		display: none;
	}

	.calendar-overflow {
		display: block;
		width: 100%;
		padding: 2px 4px;
		margin-top: 2px;
		border: none;
		background: none;
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--primary-600, #2563eb);
		cursor: pointer;
		text-align: left;
		border-radius: var(--radius-sm, 0.25rem);
		transition: background 0.1s ease;
	}

	.calendar-overflow:hover {
		background: var(--primary-50, #eff6ff);
	}

	.expand-all-btn {
		margin-left: 1rem;
	}

	/* Calendar header navigation */
	.calendar-top-nav {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.calendar-nav-buttons {
		display: flex;
		gap: 1rem;
	}

	/* Mobile calendar: hidden on desktop */
	.mobile-calendar {
		display: none;
	}

	/* Week strip layout */
	.week-strip-headers {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
		margin-bottom: 2px;
	}

	.week-strip-header {
		text-align: center;
		font-size: 0.6875rem;
		font-weight: 600;
		color: var(--text-muted, #9ca3af);
		padding: 2px 0;
	}

	.week-strip-grid {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 4px;
		margin-bottom: 16px;
	}

	.day-pill {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 3px;
		padding: 8px 4px 6px;
		border: 2px solid var(--border-color, #e5e7eb);
		border-radius: var(--radius, 0.5rem);
		background: var(--bg-card, #fff);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.day-pill:hover {
		background: var(--primary-50, #eff6ff);
		border-color: var(--primary-300, #93c5fd);
	}

	.day-pill.today {
		border-color: var(--primary-500, #3b82f6);
	}

	.day-pill.selected {
		background: var(--primary-500, #3b82f6);
		color: white;
		border-color: var(--primary-600, #2563eb);
	}

	.day-pill-date {
		font-size: 0.875rem;
		font-weight: 600;
		line-height: 1;
	}

	.task-dot {
		width: 5px;
		height: 5px;
		border-radius: 50%;
		background-color: var(--primary-500, #3b82f6);
	}

	.task-dot-selected {
		background-color: white;
	}

	/* Selected day detail panel */
	.day-detail {
		border-top: 1px solid var(--border-color, #e5e7eb);
		padding-top: 12px;
	}

	.day-detail-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
	}

	.day-detail-title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--text-primary, #1f2937);
	}

	.day-detail-count {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--text-muted, #9ca3af);
	}

	.day-detail-empty {
		text-align: center;
		padding: 32px 16px;
		color: var(--text-muted, #9ca3af);
		font-size: 0.875rem;
	}

	.day-detail-tasks {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	/* Mobile task cards */
	.mobile-task-card {
		padding: 12px;
		border-radius: var(--radius-sm, 0.25rem);
		cursor: pointer;
		transition: box-shadow 0.15s ease;
		color: #1f2937;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
	}

	.mobile-task-card:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
	}

	.mobile-task-title {
		font-size: 0.9375rem;
		font-weight: 500;
		margin-bottom: 4px;
	}

	.mobile-task-meta {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.75rem;
	}

	.mobile-task-priority {
		text-transform: capitalize;
		font-weight: 500;
		color: var(--text-secondary, #6b7280);
	}

	.mobile-task-deadline {
		font-weight: 700;
		text-transform: uppercase;
		font-size: 0.625rem;
		letter-spacing: 0.04em;
	}

	.mobile-task-subtasks {
		font-weight: 600;
		color: var(--text-secondary, #6b7280);
		background: rgba(0, 0, 0, 0.06);
		padding: 0 0.25rem;
		border-radius: 3px;
	}

	.mobile-subtask-parent {
		font-size: 0.6875rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		margin: -12px -12px 8px -12px;
		padding: 4px 12px;
		border-radius: var(--radius-sm, 0.25rem) var(--radius-sm, 0.25rem) 0 0;
	}

	/* Responsive: show mobile calendar, hide desktop on small screens */
	@media (max-width: 768px) {
		.mobile-calendar {
			display: block;
		}

		.calendar-nav-buttons {
			gap: 0.5rem;
		}

		.calendar-top-nav {
			flex-wrap: wrap;
			gap: 0.5rem;
		}

		.expand-all-btn {
			display: none;
		}
	}
</style>
