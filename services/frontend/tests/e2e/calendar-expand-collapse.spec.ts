/**
 * E2E Test: Calendar Expand All / Collapse All
 *
 * Tests the expand/collapse all button that toggles visibility
 * of overflowed tasks ("+X more") across all calendar days.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin, createTodoViaAPI, getTodayDate } from '../helpers/test-utils';

test.describe('Calendar Expand/Collapse All', () => {
	// Use today's date so tasks always appear in the visible calendar window
	const dueDate = getTodayDate();

	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('expand all button is hidden when no days overflow', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });
		await expect(page.locator('.expand-all-btn')).not.toBeVisible();
	});

	test('expand all button appears when a day has more than 3 tasks', async ({ page }) => {
		// Create 4 tasks on the same day to trigger overflow (MAX_VISIBLE_TASKS = 3)
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Overflow Task ${i}`, { dueDate });
		}

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Wait for at least one task to render on the calendar, confirming data has loaded
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-task').first()).toBeVisible({ timeout: 15000 });

		await expect(page.locator('.expand-all-btn')).toBeVisible({ timeout: 10000 });
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');
	});

	test('clicking expand all shows all tasks and changes label to collapse all', async ({
		page
	}) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Toggle Task ${i}`, { dueDate });
		}

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Wait for overflow indicator to appear (confirms tasks are loaded and overflowing)
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 15000 });

		// Click Expand All
		await page.locator('.expand-all-btn').click();

		// Button should now say Collapse All
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		// The "+X more" overflow indicator should be gone, replaced by "Show less"
		await expect(dayCell.locator('.calendar-overflow')).toContainText('Show less');

		// The 4th task (index 3) should now be visible after expanding
		await expect(dayCell.locator('.calendar-task').nth(3)).toBeVisible();
	});

	test('clicking collapse all hides overflowed tasks again', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Collapse Task ${i}`, { dueDate });
		}

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Wait for tasks to load and expand button to appear
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 15000 });

		// Expand, then collapse
		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');

		// Overflow indicator should be back
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more');
	});

	test('manually expanding all overflowing days syncs button to collapse all', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Sync Task ${i}`, { dueDate });
		}

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Wait for expand button
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 15000 });
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');

		// Manually expand the one overflowing day
		await dayCell.locator('.calendar-overflow').click();

		// Since all overflowing days are now expanded, button should say Collapse All
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');
	});

	test('week navigation resets expanded state', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Nav Task ${i}`, { dueDate });
		}

		await page.goto('/');
		await page.waitForSelector('#drag-drop-calendar', { timeout: 15000 });

		// Wait for expand button and expand all
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 15000 });
		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		// Navigate to next week and back
		await page.locator('button:has-text("Next")').click();
		await page.locator('button:has-text("Previous")').click();

		// After navigating back, expandedDays was reset so the overflow should be collapsed
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more', { timeout: 15000 });
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');
	});
});
