/**
 * E2E Tests: UX Improvements
 *
 * Tests for search modal, toast notifications with undo,
 * task summary stats bar, calendar Today button and overflow,
 * and user dropdown click behavior.
 */

import { test, expect } from '@playwright/test';
import {
	registerAndLogin,
	createTodoViaAPI,
	getTodayDate,
	getPastDate,
	getFutureDate
} from '../helpers/test-utils';

test.describe('Search Modal', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should open search modal with Ctrl+K and close with Escape', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Modal should not be visible initially
		await expect(page.locator('.search-backdrop')).not.toBeVisible();

		// Open with Ctrl+K
		await page.keyboard.press('Control+k');
		await expect(page.locator('.search-modal')).toBeVisible();
		await expect(page.locator('.search-input')).toBeFocused();

		// Close with Escape
		await page.keyboard.press('Escape');
		await expect(page.locator('.search-backdrop')).not.toBeVisible();
	});

	test('should open search modal via toolbar button', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.click('.search-trigger');
		await expect(page.locator('.search-modal')).toBeVisible();
	});

	test('should search and display results', async ({ page }) => {
		// Create a task to search for
		await createTodoViaAPI(page, 'Searchable Unique Task XYZ');

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Open search and type
		await page.keyboard.press('Control+k');
		await page.fill('.search-input', 'Searchable Unique Task XYZ');

		// Wait for results (debounced)
		await expect(page.locator('.search-result')).toBeVisible({ timeout: 5000 });
		await expect(
			page.locator('.result-title', { hasText: 'Searchable Unique Task XYZ' })
		).toBeVisible();
	});

	test('should show no results message', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.keyboard.press('Control+k');
		await page.fill('.search-input', 'nonexistenttaskxyzabc123');

		// Wait for "No results" state
		await expect(page.locator('.search-state', { hasText: 'No results found' })).toBeVisible({
			timeout: 5000
		});
	});

	test('should navigate to task on result click', async ({ page }) => {
		await createTodoViaAPI(page, 'Navigate Test Task');

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.keyboard.press('Control+k');
		await page.fill('.search-input', 'Navigate Test Task');

		await expect(page.locator('.search-result')).toBeVisible({ timeout: 5000 });
		await page.click('.search-result');

		// Should navigate to task detail page
		await expect(page).toHaveURL(/\/task\/\d+/);
	});

	test('should close search modal on backdrop click', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.keyboard.press('Control+k');
		await expect(page.locator('.search-modal')).toBeVisible();

		// Click on backdrop (outside modal)
		await page.locator('.search-backdrop').click({ position: { x: 10, y: 10 } });
		await expect(page.locator('.search-backdrop')).not.toBeVisible();
	});
});

test.describe('Toast Notifications and Undo', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should show undo toast on task completion from todos page', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Complete Me For Undo', { dueDate: today });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Switch to list view to access the complete button
		await page.click('button:has-text("List View")');

		// Wait for the task to appear in the list (task titles are plain divs, not .task-title)
		const taskRow = page.locator('#list-view').getByText('Complete Me For Undo');
		await expect(taskRow).toBeVisible({ timeout: 5000 });

		// Click the complete button on the task's row
		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Complete Me For Undo' });
		await taskCard.locator('.btn-success').click();

		// Toast should appear with Undo button
		await expect(page.locator('.toast')).toBeVisible({ timeout: 5000 });
		await expect(page.locator('.toast-message', { hasText: 'Task completed' })).toBeVisible();
		await expect(page.locator('.toast-action', { hasText: 'Undo' })).toBeVisible();
	});

	test('should restore task when clicking Undo', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Undo This Task', { dueDate: today });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Switch to list view
		await page.click('button:has-text("List View")');
		const taskRow = page.locator('#list-view').getByText('Undo This Task');
		await expect(taskRow).toBeVisible({ timeout: 5000 });

		// Complete the task
		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Undo This Task' });
		await taskCard.locator('.btn-success').click();

		// Wait for toast
		await expect(page.locator('.toast-action', { hasText: 'Undo' })).toBeVisible({ timeout: 5000 });

		// Click Undo
		await page.click('.toast-action');

		// Task should reappear in the list
		await expect(page.locator('#list-view').getByText('Undo This Task')).toBeVisible({
			timeout: 5000
		});
	});

	test('should show undo toast on home page completion', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Home Undo Task', { dueDate: today });

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.task-title', { hasText: 'Home Undo Task' })).toBeVisible({
			timeout: 5000
		});

		// Click the complete button
		await page.locator('.complete-btn').first().click();

		// Toast should appear
		await expect(page.locator('.toast-message', { hasText: 'Task completed' })).toBeVisible({
			timeout: 5000
		});
		await expect(page.locator('.toast-action', { hasText: 'Undo' })).toBeVisible();
	});

	test('should dismiss toast with close button', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Dismiss Toast Task', { dueDate: today });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');
		const taskRow = page.locator('#list-view').getByText('Dismiss Toast Task');
		await expect(taskRow).toBeVisible({ timeout: 5000 });

		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Dismiss Toast Task' });
		await taskCard.locator('.btn-success').click();
		await expect(page.locator('.toast')).toBeVisible({ timeout: 5000 });

		// Click dismiss
		await page.click('.toast-dismiss');
		await expect(page.locator('.toast')).not.toBeVisible();
	});
});

test.describe('Task Summary Stats Bar', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should display summary stats bar with total count', async ({ page }) => {
		await createTodoViaAPI(page, 'Stats Task 1');
		await createTodoViaAPI(page, 'Stats Task 2');

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.summary-bar')).toBeVisible({ timeout: 5000 });
		// Total should include at least the 2 tasks we created
		await expect(page.locator('.summary-stat').first()).toBeVisible();
	});

	test('should show overdue count when tasks are overdue', async ({ page }) => {
		const yesterday = getPastDate(1);
		await createTodoViaAPI(page, 'Overdue Stats Task', { dueDate: yesterday });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.summary-overdue')).toBeVisible({ timeout: 5000 });
	});

	test('should show due today count', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Today Stats Task', { dueDate: today });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.summary-today')).toBeVisible({ timeout: 5000 });
	});
});

test.describe('Calendar Improvements', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should have Today button in calendar navigation', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Default view is calendar
		await expect(page.locator('button:has-text("Today")')).toBeVisible();
		await expect(page.locator('button:has-text("← Previous")')).toBeVisible();
		await expect(page.locator('button:has-text("Next →")')).toBeVisible();
	});

	test('should navigate to current week with Today button', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Navigate away from current week
		await page.click('button:has-text("Next →")');
		await page.click('button:has-text("Next →")');

		// Click Today to return
		await page.click('button:has-text("Today")');

		// Today's cell should be highlighted
		await expect(page.locator('.calendar-day.today')).toBeVisible();
	});

	test('should open task detail on single click in calendar', async ({ page }) => {
		const tomorrow = getFutureDate(1);
		await createTodoViaAPI(page, 'Calendar Click Task', { dueDate: tomorrow });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Wait for task to appear in calendar
		const calendarTask = page.locator('.calendar-task', { hasText: 'Calendar Click Task' });
		await expect(calendarTask).toBeVisible({ timeout: 5000 });

		// Single click should open detail panel
		await calendarTask.click();

		// Task detail panel should open
		await expect(page.locator('.panel-container')).toBeVisible({ timeout: 5000 });
	});

	test('should show +N more when calendar day has many tasks', async ({ page }) => {
		const tomorrow = getFutureDate(1);
		// Create 5 tasks for the same day to trigger overflow (MAX_VISIBLE_TASKS = 3)
		await createTodoViaAPI(page, 'Overflow Task 1', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Overflow Task 2', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Overflow Task 3', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Overflow Task 4', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Overflow Task 5', { dueDate: tomorrow });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Wait for at least one visible calendar task to confirm data loaded
		await expect(page.locator('.calendar-task:not(.calendar-task-hidden)').first()).toBeVisible({
			timeout: 10000
		});

		// Should see +N more button since we have 5 tasks and MAX_VISIBLE_TASKS = 3
		await expect(page.locator('.calendar-overflow')).toBeVisible({ timeout: 5000 });
		const overflowText = await page.locator('.calendar-overflow').first().textContent();
		expect(overflowText).toMatch(/\+\d+ more/);
	});

	test('should expand and collapse overflow tasks', async ({ page }) => {
		const tomorrow = getFutureDate(1);
		await createTodoViaAPI(page, 'Expand Task 1', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Expand Task 2', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Expand Task 3', { dueDate: tomorrow });
		await createTodoViaAPI(page, 'Expand Task 4', { dueDate: tomorrow });

		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Wait for at least one visible calendar task to confirm data loaded
		await expect(page.locator('.calendar-task:not(.calendar-task-hidden)').first()).toBeVisible({
			timeout: 10000
		});

		// Should see overflow button since we have 4 tasks and MAX_VISIBLE_TASKS = 3
		await expect(page.locator('.calendar-overflow')).toBeVisible({ timeout: 5000 });

		// Click to expand
		await page.locator('.calendar-overflow').first().click();

		// After expanding, should show "Show less"
		await expect(page.locator('.calendar-overflow', { hasText: 'Show less' })).toBeVisible({
			timeout: 3000
		});

		// Click to collapse
		await page.locator('.calendar-overflow', { hasText: 'Show less' }).click();

		// Should show "+N more" again
		await expect(page.locator('.calendar-overflow', { hasText: /\+\d+ more/ })).toBeVisible({
			timeout: 3000
		});
	});
});

test.describe('User Dropdown Menu', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should open user dropdown on click', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Dropdown should be closed
		await expect(page.locator('[data-testid=logout-button]')).not.toBeVisible();

		// Click to open
		await page.click('.user-dropdown-trigger');
		await expect(page.locator('[data-testid=logout-button]')).toBeVisible({ timeout: 3000 });
	});

	test('should close user dropdown on outside click', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Open dropdown
		await page.click('.user-dropdown-trigger');
		await expect(page.locator('[data-testid=logout-button]')).toBeVisible({ timeout: 3000 });

		// Click outside
		await page.click('h1:has-text("Task Manager")');
		await expect(page.locator('[data-testid=logout-button]')).not.toBeVisible();
	});

	test('should toggle user dropdown on repeated clicks', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		// Open
		await page.click('.user-dropdown-trigger');
		await expect(page.locator('[data-testid=logout-button]')).toBeVisible({ timeout: 3000 });

		// Close via toggle
		await page.click('.user-dropdown-trigger');
		await expect(page.locator('[data-testid=logout-button]')).not.toBeVisible();
	});

	test('should show settings link in dropdown', async ({ page }) => {
		await page.goto('/tasks');
		await page.waitForLoadState('networkidle');

		await page.click('.user-dropdown-trigger');
		await expect(page.locator('.dropdown-item', { hasText: 'Settings' })).toBeVisible({
			timeout: 3000
		});
	});
});
