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
	import type { Todo, TodoFilters } from '$lib/types';

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
	let todosByDate: Record<string, Todo[]> = {};
	// Track drag operation state
	let draggedTodoId: number | null = null;
	let originalDate: string | null = null;
	let isDragging = false;
	// Per-day expand state for overflow
	let expandedDays: Record<string, boolean> = {};
	// Mobile: selected day for detail view
	let selectedDay: string = formatDateForInput(new Date());

	interface CalendarSubtaskItem {
		id: number;
		title: string;
		priority: 'low' | 'medium' | 'high' | 'urgent';
		status: string;
		due_date: string;
		parentId: number;
		parentTitle: string;
		parentColor: string | null;
	}

	let subtasksByDate: Record<string, CalendarSubtaskItem[]> = {};

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

	// Selected day data for mobile detail view
	$: selectedDayTasks = todosByDate[selectedDay] || [];
	$: selectedDaySubtasks = subtasksByDate[selectedDay] || [];

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

	function groupTodosByDate(todosList: Todo[]): Record<string, Todo[]> {
		const grouped: Record<string, Todo[]> = {};
		const subtaskGrouped: Record<string, CalendarSubtaskItem[]> = {};

		// Initialize arrays for all visible dates
		for (const day of days) {
			grouped[day.dateStr] = [];
			subtaskGrouped[day.dateStr] = [];
		}

		// Add todos to their respective dates
		todosList.forEach((todo) => {
			if (todo.due_date) {
				const dateStr = todo.due_date.split('T')[0];
				if (!grouped[dateStr]) grouped[dateStr] = [];
				grouped[dateStr].push(todo);
			}

			// Extract pending subtasks as separate calendar items
			const parentDueDate = todo.due_date ? todo.due_date.split('T')[0] : null;
			(todo.subtasks || []).forEach((subtask) => {
				if (subtask.status === 'completed') return;
				const dateStr = subtask.due_date ? subtask.due_date.split('T')[0] : parentDueDate;
				if (!dateStr) return;
				if (!subtaskGrouped[dateStr]) subtaskGrouped[dateStr] = [];
				subtaskGrouped[dateStr].push({
					id: subtask.id,
					title: subtask.title,
					priority: subtask.priority,
					status: subtask.status,
					due_date: dateStr,
					parentId: todo.id,
					parentTitle: todo.title,
					parentColor: todo.project_color || null
				});
			});
		});

		subtasksByDate = subtaskGrouped;
		return grouped;
	}

	function handleConsider(dateStr: string, event: CustomEvent<DndEvent<Todo>>) {
		// Track what's being dragged when drag starts
		if (event.detail.info.trigger === 'dragStarted') {
			isDragging = true;
			const draggedId = event.detail.info.id;
			// Convert draggedId to number for comparison with todo.id
			const draggedIdNum = typeof draggedId === 'string' ? parseInt(draggedId, 10) : draggedId;
			// Find the todo being dragged across all dates
			for (const [date, todosInDate] of Object.entries(todosByDate)) {
				if (todosInDate) {
					const todo = todosInDate.find((t) => t && t.id === draggedIdNum);
					if (todo && todo.due_date) {
						draggedTodoId = draggedIdNum;
						originalDate = todo.due_date.split('T')[0];
						break;
					}
				}
			}
		}

		// Update local state - svelte-dnd-action gives us the new items array for this date
		// This is what the date WILL look like if the drag completes
		todosByDate = { ...todosByDate, [dateStr]: event.detail.items as Todo[] };
	}

	async function handleFinalize(dateStr: string, event: CustomEvent<DndEvent<Todo>>) {
		// Update local state first - this is what svelte-dnd-action expects
		todosByDate = { ...todosByDate, [dateStr]: event.detail.items as Todo[] };

		// Only make API call if item was actually moved to a different date
		if (draggedTodoId !== null && originalDate !== null && originalDate !== dateStr) {
			const todoId = draggedTodoId;

			try {
				// Make API call while still blocking store subscriptions
				await todos.updateTodo(todoId, { due_date: dateStr });

				// After API succeeds, manually rebuild from store to get authoritative data
				const currentTodos = get(pendingTodos);
				todosByDate = groupTodosByDate(currentTodos);

				// Clear drag tracking AFTER manual rebuild to prevent subscription race
				isDragging = false;
				draggedTodoId = null;
				originalDate = null;
			} catch (error) {
				logger.error('Failed to update todo date:', error);
				// Reload all todos to revert the change
				await todos.load({ status: 'pending', ...filters });
				const currentTodos = get(pendingTodos);
				todosByDate = groupTodosByDate(currentTodos);

				// Clear drag tracking after error recovery
				isDragging = false;
				draggedTodoId = null;
				originalDate = null;
			}
		} else {
			// Item was dropped in same column or drag cancelled
			// Just clear drag state - local state already updated above
			isDragging = false;
			draggedTodoId = null;
			originalDate = null;
		}
	}

	function prevWeek() {
		const newDate = new Date(currentWeekStart);
		newDate.setDate(newDate.getDate() - 7);
		currentWeekStart = newDate;
	}

	function nextWeek() {
		const newDate = new Date(currentWeekStart);
		newDate.setDate(newDate.getDate() + 7);
		currentWeekStart = newDate;
	}

	function goToToday() {
		const thisWeekMonday = getStartOfWeek(new Date());
		thisWeekMonday.setDate(thisWeekMonday.getDate() - 7);
		currentWeekStart = thisWeekMonday;
		selectedDay = formatDateForInput(new Date());
	}

	function handleEditTodo(todo: Todo) {
		dispatch('editTodo', todo);
	}

	function handleTaskClick(todo: Todo) {
		// Always open task detail on single click (desktop and touch)
		if (!isDragging) {
			handleEditTodo(todo);
		}
	}

	function toggleDayExpand(dateStr: string) {
		expandedDays = { ...expandedDays, [dateStr]: !expandedDays[dateStr] };
	}

	onMount(() => {
		// Subscribe to pendingTodos and rebuild the calendar whenever it changes
		// But don't update during drag operations to avoid interfering with the drag
		const unsubscribe = pendingTodos.subscribe((value) => {
			if (!isDragging) {
				todosByDate = groupTodosByDate(value);
			}
		});

		// Load initial todos
		todos.load({ status: 'pending', ...filters });

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
				{@const taskCount =
					(todosByDate[dateStr] || []).length + (subtasksByDate[dateStr] || []).length}
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
					{#each selectedDayTasks as todo (todo.id)}
						{@const subtasks = todo.subtasks || []}
						{@const completedSubtaskCount = subtasks.filter((s) => s.status === 'completed').length}
						<div
							class="mobile-task-card"
							style="border-left: 4px solid {todo.project_color ||
								DEFAULT_PROJECT_COLOR}; background-color: {hexTo50Shade(
								todo.project_color || DEFAULT_PROJECT_COLOR
							)}"
							on:click={() => handleTaskClick(todo)}
							role="button"
							tabindex="0"
							on:keydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') handleTaskClick(todo);
							}}
						>
							<div class="mobile-task-title">{todo.title}</div>
							<div class="mobile-task-meta">
								<span class="mobile-task-priority">{todo.priority}</span>
								{#if todo.deadline_type && todo.deadline_type !== 'preferred'}
									<span
										class="mobile-task-deadline"
										style="color: {getDeadlineTypeColor(todo.deadline_type)}"
									>
										{getDeadlineTypeLabel(todo.deadline_type)}
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
				{@const allTasks = todosByDate[dateStr] || []}
				{@const isExpanded = expandedDays[dateStr] || false}
				{@const hiddenCount = Math.max(0, allTasks.length - MAX_VISIBLE_TASKS)}
				{@const pendingSubtasks = subtasksByDate[dateStr] || []}
				{@const freeSlots = Math.max(0, MAX_VISIBLE_TASKS - allTasks.length)}
				{@const visibleSubtaskCount = isExpanded ? pendingSubtasks.length : Math.min(pendingSubtasks.length, freeSlots)}
				{@const overflow = isExpanded ? 0 : hiddenCount + (pendingSubtasks.length - visibleSubtaskCount)}
				<div class="calendar-day" class:today={isTodayDay} data-date={dateStr}>
					<div class="calendar-date">
						{date.getMonth() + 1}/{date.getDate()}
					</div>
					<div
						class="tasks-container"
						use:dndzone={{
							items: todosByDate[dateStr] || [],
							dropTargetStyle: { outline: '2px dashed #3b82f6' },
							type: 'todo',
							flipDurationMs: 200
						}}
						on:consider={(e) => handleConsider(dateStr, e)}
						on:finalize={(e) => handleFinalize(dateStr, e)}
					>
						{#each allTasks as todo, idx (todo.id)}
							{@const isHidden = !isExpanded && idx >= MAX_VISIBLE_TASKS}
							{@const subtasks = todo.subtasks || []}
							{@const completedSubtaskCount = subtasks.filter(
								(s) => s.status === 'completed'
							).length}
							<div
								class="calendar-task {todo.priority}-priority"
								class:calendar-task-hidden={isHidden}
								style="background-color: {hexTo50Shade(
									todo.project_color || DEFAULT_PROJECT_COLOR
								)}; border-left: 4px solid {todo.project_color || DEFAULT_PROJECT_COLOR}"
								on:click={() => handleTaskClick(todo)}
								role="button"
								tabindex="0"
								on:keydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										handleEditTodo(todo);
									}
								}}
							>
								<div class="task-title">{todo.title}</div>
								{#if (todo.deadline_type && todo.deadline_type !== 'preferred') || subtasks.length > 0}
									<div class="calendar-task-meta">
										{#if todo.deadline_type && todo.deadline_type !== 'preferred'}
											<span
												class="calendar-deadline-type"
												style="color: {getDeadlineTypeColor(todo.deadline_type)}"
												title="{getDeadlineTypeLabel(todo.deadline_type)} deadline"
											>
												{getDeadlineTypeLabel(todo.deadline_type)}
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
						{/each}
					</div>
					{#each pendingSubtasks as subtask, idx (subtask.id)}
						{#if isExpanded || idx < visibleSubtaskCount}
							<div
								class="calendar-task calendar-subtask-item {subtask.priority}-priority"
								style="background-color: {hexTo50Shade(
									subtask.parentColor || DEFAULT_PROJECT_COLOR
								)}; border-left: 4px solid {subtask.parentColor || DEFAULT_PROJECT_COLOR}"
								on:click={() => goto(`/task/${subtask.id}`)}
								role="button"
								tabindex="0"
								on:keydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') goto(`/task/${subtask.id}`);
								}}
							>
								<div
									class="calendar-subtask-parent"
									style="background-color: {subtask.parentColor ||
										DEFAULT_PROJECT_COLOR}; color: {contrastText(
										subtask.parentColor || DEFAULT_PROJECT_COLOR
									)}"
								>
									#{subtask.parentId}
									{subtask.parentTitle}
								</div>
								<div class="task-title">{subtask.title}</div>
							</div>
						{/if}
					{/each}
					{#if overflow > 0}
						<button class="calendar-overflow" on:click={() => toggleDayExpand(dateStr)}>
							+{overflow} more
						</button>
					{:else if isExpanded && (allTasks.length > MAX_VISIBLE_TASKS || (subtasksByDate[dateStr] || []).length > 0)}
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
	}
</style>
