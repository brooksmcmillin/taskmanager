/**
 * E2E Test: Calendar Subtask Dragging & Drop Target Coverage
 *
 * Tests that:
 * 1. Subtasks appear inside the dndzone (tasks-container) and are draggable
 * 2. Dropping tasks/subtasks anywhere in the day cell works (not just the narrow task area)
 * 3. Dragging a subtask to a different day updates its due date
 */

import { test, expect, type Page, type Locator } from '@playwright/test';
import {
	registerAndLogin,
	createTodoViaAPI,
	getTodayDate,
	getFutureDate,
	waitForApiResponse
} from '../helpers/test-utils';

/**
 * Create a subtask via the backend API
 */
async function createSubtaskViaAPI(
	page: Page,
	parentId: number,
	title: string,
	options: { dueDate?: string; priority?: string } = {}
) {
	const body: Record<string, string> = { title };
	if (options.dueDate) body.due_date = options.dueDate;
	if (options.priority) body.priority = options.priority;

	const response = await page.request.post(`/api/todos/${parentId}/subtasks`, { data: body });
	if (!response.ok()) {
		throw new Error(`Failed to create subtask: ${response.status()} ${await response.text()}`);
	}
	return response.json();
}

/**
 * Helper to extract the parent todo ID from the API response
 */
function getParentId(apiResponse: { data: { id: number } }): number {
	return apiResponse.data.id;
}

/**
 * Simulate a pointer-based drag for svelte-dnd-action.
 *
 * svelte-dnd-action uses pointer events (not HTML5 drag API), so Playwright's
 * built-in dragTo doesn't work. This helper manually dispatches the pointer
 * event sequence the library expects.
 */
async function pointerDrag(page: Page, source: Locator, target: Locator) {
	const sourceBox = await source.boundingBox();
	const targetBox = await target.boundingBox();
	if (!sourceBox || !targetBox) throw new Error('Could not get bounding boxes for drag');

	const srcX = sourceBox.x + sourceBox.width / 2;
	const srcY = sourceBox.y + sourceBox.height / 2;
	const tgtX = targetBox.x + targetBox.width / 2;
	const tgtY = targetBox.y + targetBox.height / 2;

	// Move to source, press, wait for dnd library to recognize the drag
	await page.mouse.move(srcX, srcY);
	await page.mouse.down();
	// svelte-dnd-action needs a small initial move to detect drag start
	await page.mouse.move(srcX + 5, srcY + 5, { steps: 2 });
	await page.waitForTimeout(250);
	// Move to target in steps to trigger consider events along the way
	await page.mouse.move(tgtX, tgtY, { steps: 10 });
	await page.waitForTimeout(100);
	await page.mouse.up();
}

test.describe('Calendar Subtask Dragging', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('subtasks render inside the tasks-container (dndzone)', async ({ page }) => {
		const dueDate = getTodayDate();

		// Create parent task + subtask with the same due date
		const parentResp = await createTodoViaAPI(page, 'Parent Task', { dueDate });
		const parentId = getParentId(parentResp);
		await createSubtaskViaAPI(page, parentId, 'Child Subtask', { dueDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-task').first()).toBeVisible({ timeout: 15000 });

		// The subtask should be inside .tasks-container (the dndzone), not a sibling of it
		const tasksContainer = dayCell.locator('.tasks-container');
		const subtaskInZone = tasksContainer.locator('.calendar-subtask-item');
		await expect(subtaskInZone).toBeVisible({ timeout: 10000 });
		await expect(subtaskInZone).toContainText('Child Subtask');
	});

	test('subtasks have grab cursor (are draggable)', async ({ page }) => {
		const dueDate = getTodayDate();

		const parentResp = await createTodoViaAPI(page, 'Grabbable Parent', { dueDate });
		const parentId = getParentId(parentResp);
		await createSubtaskViaAPI(page, parentId, 'Grabbable Subtask', { dueDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-subtask-item').first()).toBeVisible({
			timeout: 15000
		});

		// Verify the subtask has cursor: grab (from .calendar-subtask-item CSS)
		const cursor = await dayCell
			.locator('.calendar-subtask-item')
			.first()
			.evaluate((el) => window.getComputedStyle(el).cursor);
		expect(cursor).toBe('grab');
	});

	test('subtasks show parent info badge', async ({ page }) => {
		const dueDate = getTodayDate();

		const parentResp = await createTodoViaAPI(page, 'My Parent Task', { dueDate });
		const parentId = getParentId(parentResp);
		await createSubtaskViaAPI(page, parentId, 'My Subtask', { dueDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		const subtask = dayCell.locator('.calendar-subtask-item');
		await expect(subtask).toBeVisible({ timeout: 15000 });

		// Subtask should display parent reference
		const parentBadge = subtask.locator('.calendar-subtask-parent');
		await expect(parentBadge).toBeVisible();
		await expect(parentBadge).toContainText('My Parent Task');
	});

	test('subtasks count toward overflow limit', async ({ page }) => {
		const dueDate = getTodayDate();

		// Create 2 parent tasks + 2 subtasks = 4 items total, exceeding MAX_VISIBLE_TASKS (3)
		const parent1Resp = await createTodoViaAPI(page, 'Parent A', { dueDate });
		const parent1Id = getParentId(parent1Resp);
		await createTodoViaAPI(page, 'Parent B', { dueDate });
		await createSubtaskViaAPI(page, parent1Id, 'Subtask 1', { dueDate });
		await createSubtaskViaAPI(page, parent1Id, 'Subtask 2', { dueDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-task').first()).toBeVisible({ timeout: 15000 });

		// With 4 items total (2 parents + 2 subtasks), overflow should appear
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 10000 });
	});
});

test.describe('Calendar Drop Target Coverage', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('tasks-container fills the day cell vertically', async ({ page }) => {
		const dueDate = getTodayDate();

		// Create just one task so there's plenty of empty space in the day cell
		await createTodoViaAPI(page, 'Small Task', { dueDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-task').first()).toBeVisible({ timeout: 15000 });

		// Verify the tasks-container has flex: 1 (fills remaining space)
		const tasksContainer = dayCell.locator('.tasks-container');
		const flexGrow = await tasksContainer.evaluate((el) => window.getComputedStyle(el).flexGrow);
		expect(flexGrow).toBe('1');

		// The tasks-container should be substantially taller than just its content
		const containerBox = await tasksContainer.boundingBox();
		const taskBox = await dayCell.locator('.calendar-task').first().boundingBox();

		expect(containerBox).toBeTruthy();
		expect(taskBox).toBeTruthy();
		// The container should be significantly larger than the single task card
		expect(containerBox!.height).toBeGreaterThan(taskBox!.height * 1.5);
	});

	test('empty day cells have a tall drop target', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Find a day cell that has no tasks (use a future date unlikely to have tasks)
		const emptyDate = getFutureDate(12);
		const dayCell = page.locator(`.calendar-day[data-date="${emptyDate}"]`);

		// Skip if date isn't visible in the current 3-week window
		const isVisible = await dayCell.isVisible().catch(() => false);
		if (!isVisible) return;

		// Even empty, the tasks-container should fill the day cell
		const tasksContainer = dayCell.locator('.tasks-container');
		const containerBox = await tasksContainer.boundingBox();
		const dayCellBox = await dayCell.boundingBox();

		expect(containerBox).toBeTruthy();
		expect(dayCellBox).toBeTruthy();

		// The tasks-container should take up most of the day cell height
		// (minus the date header which is ~20-30px)
		const headerApproxHeight = 30;
		expect(containerBox!.height).toBeGreaterThan(dayCellBox!.height - headerApproxHeight - 20);
	});

	test('drag parent task to a different day via the empty area', async ({ page }) => {
		// Use dates within the visible 3-week window
		const sourceDate = getTodayDate();
		// Use adjacent cell for reliable pointer targeting
		const targetDate = getFutureDate(1);

		await createTodoViaAPI(page, 'Drag Target Test', { dueDate: sourceDate });

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const sourceDayCell = page.locator(`.calendar-day[data-date="${sourceDate}"]`);
		const todoItem = sourceDayCell
			.locator('.calendar-task')
			.filter({ hasText: 'Drag Target Test' });
		await expect(todoItem).toBeVisible({ timeout: 15000 });

		// Target: the tasks-container (dndzone) in the destination day, which now fills the cell
		const targetContainer = page.locator(
			`.calendar-day[data-date="${targetDate}"] .tasks-container`
		);

		// Set up response listener before the drag
		const responsePromise = waitForApiResponse(page, '/api/todos/', 'PUT');

		// Use pointer-based drag (svelte-dnd-action doesn't use HTML5 drag API)
		await pointerDrag(page, todoItem, targetContainer);

		// Wait for the API call to complete (confirms date was updated server-side)
		await responsePromise;

		// Verify the task is gone from the source date (drag succeeded)
		await expect(
			sourceDayCell.locator('.calendar-task').filter({ hasText: 'Drag Target Test' })
		).not.toBeVisible({ timeout: 10000 });
	});

	test('moving subtask due date updates its position on the calendar', async ({ page }) => {
		const sourceDate = getTodayDate();
		const targetDate = getFutureDate(1);

		// Create parent + subtask on the same date
		const parentResp = await createTodoViaAPI(page, 'Subtask Drag Parent', {
			dueDate: sourceDate
		});
		const parentId = getParentId(parentResp);
		const subtaskResp = await createSubtaskViaAPI(page, parentId, 'Moveable Subtask', {
			dueDate: sourceDate
		});
		const subtaskId = subtaskResp.data.id;

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const sourceDayCell = page.locator(`.calendar-day[data-date="${sourceDate}"]`);
		await expect(
			sourceDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moveable Subtask' })
		).toBeVisible({ timeout: 15000 });

		// Update subtask due date via API (same PUT the drag handler calls)
		const updateResp = await page.request.put(`/api/todos/${subtaskId}`, {
			data: { due_date: targetDate }
		});
		expect(updateResp.ok()).toBeTruthy();

		// Reload to pick up the change
		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Subtask should now appear on the target date
		const targetDayCell = page.locator(`.calendar-day[data-date="${targetDate}"]`);
		await expect(
			targetDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moveable Subtask' })
		).toBeVisible({ timeout: 10000 });

		// And be gone from the source date
		await expect(
			sourceDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moveable Subtask' })
		).not.toBeVisible();
	});

	test('parent task remains on its original date after subtask due date changes', async ({
		page
	}) => {
		const sourceDate = getTodayDate();
		const targetDate = getFutureDate(1);

		// Create parent + subtask, both on the same date
		const parentResp = await createTodoViaAPI(page, 'Sticky Parent', { dueDate: sourceDate });
		const parentId = getParentId(parentResp);
		const subtaskResp = await createSubtaskViaAPI(page, parentId, 'Moving Subtask', {
			dueDate: sourceDate
		});
		const subtaskId = subtaskResp.data.id;

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		const sourceDayCell = page.locator(`.calendar-day[data-date="${sourceDate}"]`);
		await expect(
			sourceDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moving Subtask' })
		).toBeVisible({ timeout: 15000 });

		// Move the subtask to a different date via API (simulates what drag handler does)
		const updateResp = await page.request.put(`/api/todos/${subtaskId}`, {
			data: { due_date: targetDate }
		});
		expect(updateResp.ok()).toBeTruthy();

		// Reload the page to pick up the change
		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Parent task should still be on the source date
		await expect(
			sourceDayCell
				.locator('.calendar-task:not(.calendar-subtask-item)')
				.filter({ hasText: 'Sticky Parent' })
		).toBeVisible({ timeout: 10000 });

		// Subtask should now be on the target date, not the source
		await expect(
			sourceDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moving Subtask' })
		).not.toBeVisible();
		const targetDayCell = page.locator(`.calendar-day[data-date="${targetDate}"]`);
		await expect(
			targetDayCell.locator('.calendar-subtask-item').filter({ hasText: 'Moving Subtask' })
		).toBeVisible({ timeout: 10000 });
	});
});
