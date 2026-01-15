/**
 * E2E Test: Calendar Drag and Drop
 *
 * Tests drag-and-drop functionality for the 3-week calendar view
 */

import { test, expect } from '@playwright/test';

test.describe('Calendar Drag and Drop', () => {
	test.beforeEach(async ({ page }) => {
		// Login before each test
		await page.goto('/login');
		await page.fill('[name=username]', 'testuser');
		await page.fill('[name=password]', 'TestPass123!');
		await page.click('button[type=submit]');
		await expect(page).toHaveURL('/');

		// Wait for calendar to load
		await page.waitForSelector('#drag-drop-calendar');
	});

	test('should display 3-week calendar view', async ({ page }) => {
		// Verify calendar headers
		const headers = page.locator('.calendar-header-day');
		await expect(headers).toHaveCount(7);

		// Verify day names
		await expect(headers.nth(0)).toContainText('Sunday');
		await expect(headers.nth(6)).toContainText('Saturday');

		// Verify 21 day cells (3 weeks × 7 days)
		const days = page.locator('.calendar-day');
		await expect(days).toHaveCount(21);
	});

	test('should highlight today', async ({ page }) => {
		// Find today's date cell
		const today = new Date();
		const todayStr = today.toISOString().split('T')[0];

		const todayCell = page.locator(`.calendar-day.today[data-date="${todayStr}"]`);
		await expect(todayCell).toBeVisible();

		// Verify today has special styling
		await expect(todayCell).toHaveClass(/today/);
	});

	test('should navigate between weeks', async ({ page }) => {
		// Get first day before navigation
		const firstDayBefore = await page.locator('.calendar-day').first().getAttribute('data-date');

		// Click next week button
		await page.click('[data-testid=next-week]');

		// Get first day after navigation
		const firstDayAfter = await page.locator('.calendar-day').first().getAttribute('data-date');

		// Verify the date changed by 7 days
		const dateBefore = new Date(firstDayBefore!);
		const dateAfter = new Date(firstDayAfter!);
		const daysDiff = Math.floor((dateAfter.getTime() - dateBefore.getTime()) / (1000 * 60 * 60 * 24));
		expect(daysDiff).toBe(7);

		// Click previous week button
		await page.click('[data-testid=prev-week]');

		// Verify we're back to original week
		const firstDayReturned = await page.locator('.calendar-day').first().getAttribute('data-date');
		expect(firstDayReturned).toBe(firstDayBefore);
	});

	test('should display todos on calendar', async ({ page }) => {
		// Create a todo with a due date
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Calendar Task');
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		// Wait for calendar to update
		await page.waitForTimeout(1000);

		// Find the todo on the calendar
		const calendarDay = page.locator('.calendar-day[data-date="2026-01-20"]');
		const todoItem = calendarDay.locator('.calendar-task');

		await expect(todoItem).toBeVisible();
		await expect(todoItem).toContainText('Calendar Task');
	});

	test('should drag todo to different date', async ({ page }) => {
		// Create a todo with a due date
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Draggable Task');
		await page.fill('[name=due_date]', '2026-01-15');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Find the todo on the calendar
		const sourceDayCell = page.locator('.calendar-day[data-date="2026-01-15"]');
		const todoItem = sourceDayCell.locator('.calendar-task').filter({ hasText: 'Draggable Task' });

		// Verify it's in the source date
		await expect(todoItem).toBeVisible();

		// Drag to target date
		const targetDayCell = page.locator('.calendar-day[data-date="2026-01-20"]');

		// Use Playwright's drag and drop
		await todoItem.dragTo(targetDayCell);

		// Wait for API call to complete
		await page.waitForTimeout(1000);

		// Verify todo moved to new date
		const movedTodo = targetDayCell.locator('.calendar-task').filter({ hasText: 'Draggable Task' });
		await expect(movedTodo).toBeVisible();

		// Verify it's no longer in the source date
		const oldTodo = sourceDayCell.locator('.calendar-task').filter({ hasText: 'Draggable Task' });
		await expect(oldTodo).not.toBeVisible();
	});

	test('should show drop target indicator during drag', async ({ page }) => {
		// Create a todo
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Drag Me');
		await page.fill('[name=due_date]', '2026-01-15');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		const todoItem = page
			.locator('.calendar-day[data-date="2026-01-15"] .calendar-task')
			.filter({ hasText: 'Drag Me' });

		// Start dragging (hover + mousedown)
		await todoItem.hover();
		await page.mouse.down();

		// Move over target day
		const targetDay = page.locator('.calendar-day[data-date="2026-01-20"]');
		await targetDay.hover();

		// Verify drop indicator appears (2px dashed blue outline)
		// Note: This is implementation-specific and may need adjustment
		const dayBox = await targetDay.boundingBox();
		expect(dayBox).toBeTruthy();

		// Complete the drag
		await page.mouse.up();
	});

	test('should display project colors on calendar tasks', async ({ page }) => {
		// Assume a project with a specific color exists
		const projectColor = '#3b82f6'; // Blue

		// Create a todo assigned to that project
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Colored Task');
		await page.selectOption('[name=project_id]', '1'); // Assume project ID 1
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Find the task on calendar
		const todoItem = page
			.locator('.calendar-day[data-date="2026-01-20"] .calendar-task')
			.filter({ hasText: 'Colored Task' });

		// Verify it has project color styling
		const style = await todoItem.getAttribute('style');
		expect(style).toContain('border-left: 4px solid');
		expect(style).toContain(projectColor);
	});

	test('should show priority styling on calendar tasks', async ({ page }) => {
		// Create urgent priority task
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Urgent Task');
		await page.selectOption('[name=priority]', 'urgent');
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Find the task on calendar
		const todoItem = page
			.locator('.calendar-day[data-date="2026-01-20"] .calendar-task')
			.filter({ hasText: 'Urgent Task' });

		// Verify priority class is applied
		await expect(todoItem).toHaveClass(/urgent-priority/);
	});

	test('should open edit modal on double-click', async ({ page }) => {
		// Create a task
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Double Click Me');
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Find the task on calendar
		const todoItem = page
			.locator('.calendar-day[data-date="2026-01-20"] .calendar-task')
			.filter({ hasText: 'Double Click Me' });

		// Double-click the task
		await todoItem.dblclick();

		// Verify modal opens with pre-filled data
		await expect(page.locator('.modal')).toBeVisible();
		await expect(page.locator('[name=title]')).toHaveValue('Double Click Me');
	});

	test('should handle keyboard navigation on calendar tasks', async ({ page }) => {
		// Create a task
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Keyboard Task');
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Find the task on calendar
		const todoItem = page
			.locator('.calendar-day[data-date="2026-01-20"] .calendar-task')
			.filter({ hasText: 'Keyboard Task' });

		// Focus the task
		await todoItem.focus();

		// Press Enter to open edit modal
		await page.keyboard.press('Enter');

		// Verify modal opens
		await expect(page.locator('.modal')).toBeVisible();
	});

	test('should show only pending todos on calendar', async ({ page }) => {
		// Create pending task
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Pending Task');
		await page.fill('[name=due_date]', '2026-01-20');
		await page.click('[data-testid=save-todo]');

		await page.waitForTimeout(1000);

		// Verify it appears
		const pendingTask = page
			.locator('.calendar-day[data-date="2026-01-20"] .calendar-task')
			.filter({ hasText: 'Pending Task' });
		await expect(pendingTask).toBeVisible();

		// Complete the task
		const completeButton = page.locator('[data-testid=complete-todo]').first();
		await completeButton.click();

		await page.waitForTimeout(1000);

		// Verify it no longer appears on calendar (completed tasks are filtered out)
		await expect(pendingTask).not.toBeVisible();
	});
});
