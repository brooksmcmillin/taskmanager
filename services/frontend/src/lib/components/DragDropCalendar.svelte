<script lang="ts">
	import { onMount, createEventDispatcher } from 'svelte';
	import { get } from 'svelte/store';
	import { dndzone } from 'svelte-dnd-action';
	import type { DndEvent } from 'svelte-dnd-action';
	import { todos, pendingTodos } from '$lib/stores/todos';
	import { hexTo50Shade } from '$lib/utils/colors';
	import { getStartOfWeek, formatDateForInput, isToday } from '$lib/utils/dates';
	import { logger } from '$lib/utils/logger';
	import { getPriorityColor } from '$lib/utils/priority';
	import type { Todo, TodoFilters } from '$lib/types';

	export let filters: TodoFilters = {};

	const DEFAULT_PROJECT_COLOR = '#6b7280';
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

	interface Day {
		date: Date;
		dateStr: string;
		isToday: boolean;
	}

	$: days = generateDays(currentWeekStart, 21);

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

		// Initialize arrays for all visible dates
		for (const day of days) {
			grouped[day.dateStr] = [];
		}

		// Add todos to their respective dates
		todosList.forEach((todo) => {
			if (todo.due_date) {
				const dateStr = todo.due_date.split('T')[0];
				if (!grouped[dateStr]) grouped[dateStr] = [];
				grouped[dateStr].push(todo);
			}
		});

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

	function handleEditTodo(todo: Todo) {
		dispatch('editTodo', todo);
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
	<div class="flex justify-between items-center mb-6">
		<h2 class="text-xl font-semibold">Task Calendar</h2>
		<div class="flex gap-4">
			<button class="btn btn-secondary btn-sm" on:click={prevWeek}>← Previous</button>
			<button class="btn btn-secondary btn-sm" on:click={nextWeek}>Next →</button>
		</div>
	</div>

	<div id="calendar-container">
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
						{#each todosByDate[dateStr] || [] as todo (todo.id)}
							<div
								class="calendar-task {todo.priority}-priority"
								style="background-color: {hexTo50Shade(
									todo.project_color || DEFAULT_PROJECT_COLOR
								)}; border-left: 4px solid {todo.project_color || DEFAULT_PROJECT_COLOR}"
								on:dblclick={() => handleEditTodo(todo)}
								role="button"
								tabindex="0"
								on:keydown={(e) => {
									if (e.key === 'Enter' || e.key === ' ') {
										handleEditTodo(todo);
									}
								}}
							>
								<div class="task-title">{todo.title}</div>
								{#if todo.subtasks && todo.subtasks.length > 0}
									<div class="calendar-subtask-indicator">
										<span class="calendar-subtask-count">{todo.subtasks.filter(s => s.status === 'completed').length}/{todo.subtasks.length}</span>
									</div>
									{#each todo.subtasks.filter(s => s.status !== 'completed') as subtask}
										<a class="calendar-subtask-row" href="/task/{subtask.id}" on:click|stopPropagation on:dblclick|stopPropagation>
											<span
												class="cal-subtask-dot"
												style="background-color: {getPriorityColor(subtask.priority)}"
											></span>
											<span class="cal-subtask-title">{subtask.title}</span>
										</a>
									{/each}
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	</div>
</div>
