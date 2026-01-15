<script lang="ts">
	import { onMount } from 'svelte';
	import { dndzone } from 'svelte-dnd-action';
	import type { DndEvent } from 'svelte-dnd-action';
	import { todos, pendingTodos } from '$lib/stores/todos';
	import { hexTo50Shade } from '$lib/utils/colors';
	import { getStartOfWeek, formatDateForInput, isToday } from '$lib/utils/dates';
	import type { Todo } from '$lib/types';

	const DEFAULT_PROJECT_COLOR = '#6b7280';

	export let onEditTodo: ((todo: Todo) => void) | null = null;

	let currentWeekStart = getStartOfWeek(new Date());
	let todoList: Todo[] = [];
	let todosByDate: Record<string, Todo[]> = {};

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
			return {
				date,
				dateStr: formatDateForInput(date),
				isToday: isToday(date.toISOString())
			};
		});
	}

	function groupTodosByDate(todosList: Todo[]): Record<string, Todo[]> {
		const grouped: Record<string, Todo[]> = {};
		todosList.forEach((todo) => {
			if (todo.due_date) {
				const dateStr = todo.due_date.split('T')[0];
				if (!grouped[dateStr]) grouped[dateStr] = [];
				grouped[dateStr].push(todo);
			}
		});
		return grouped;
	}

	$: todosByDate = groupTodosByDate(todoList);

	async function loadTodos() {
		try {
			await todos.load({ status: 'pending' });
		} catch (error) {
			console.error('Failed to load todos:', error);
		}
	}

	async function handleDrop(dateStr: string, event: CustomEvent<DndEvent>) {
		const items = event.detail.items as Todo[];

		// Update local state
		todosByDate[dateStr] = items;

		// If this is the finalize event (actual drop, not just dragging over)
		if (event.type === 'finalize') {
			const movedTodo = items.find((item) => {
				const originalDate = item.due_date?.split('T')[0];
				return originalDate !== dateStr;
			});

			if (movedTodo) {
				try {
					// Store's updateTodo already updates local state, no need to reload all todos
					await todos.updateTodo(movedTodo.id, { due_date: dateStr });
				} catch (error) {
					console.error('Failed to update todo date:', error);
				}
			}
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
		if (onEditTodo) {
			onEditTodo(todo);
		}
	}

	onMount(() => {
		// Use the pendingTodos derived store instead of filtering locally
		const unsubscribe = pendingTodos.subscribe((value) => {
			todoList = value;
		});

		loadTodos();

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
			{#each ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as day}
				<div class="calendar-header-day">{day}</div>
			{/each}
		</div>

		<div id="calendar-grid">
			{#each days as { date, dateStr, isToday: isTodayDay }}
				<div
					class="calendar-day"
					class:today={isTodayDay}
					data-date={dateStr}
					use:dndzone={{
						items: todosByDate[dateStr] || [],
						dropTargetStyle: { outline: '2px dashed #3b82f6' },
						type: 'todo'
					}}
					on:consider={(e) => handleDrop(dateStr, e)}
					on:finalize={(e) => handleDrop(dateStr, e)}
				>
					<div class="calendar-date">
						{date.getMonth() + 1}/{date.getDate()}
					</div>
					<div class="tasks-container">
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
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	</div>
</div>
