/**
 * E2E Test: Calendar Expand All / Collapse All
 *
 * Tests the expand/collapse all button that toggles visibility
 * of overflowed tasks ("+X more") across all calendar days.
 */

import { test, expect } from '@playwright/test';
import {
	registerAndLogin,
	createTodoViaAPI,
	getFutureDate,
	waitForNetworkIdle
} from '../helpers/test-utils';

test.describe('Calendar Expand/Collapse All', () => {
	const dueDate = getFutureDate(5);

	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
	});

	test('expand all button is hidden when no days overflow', async ({ page }) => {
		// With no tasks, no overflow exists
		await expect(page.locator('.expand-all-btn')).not.toBeVisible();
	});

	test('expand all button appears when a day has more than 3 tasks', async ({ page }) => {
		// Create 4 tasks on the same day to trigger overflow (MAX_VISIBLE_TASKS = 3)
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Overflow Task ${i}`, { dueDate });
		}

		// Reload to pick up new tasks
		await page.reload();
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
		await waitForNetworkIdle(page);

		await expect(page.locator('.expand-all-btn')).toBeVisible();
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');
	});

	test('clicking expand all shows all tasks and changes label to collapse all', async ({
		page
	}) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Toggle Task ${i}`, { dueDate });
		}

		await page.reload();
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Verify overflow indicator is visible before expanding
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more');

		// Click Expand All
		await page.locator('.expand-all-btn').click();

		// Button should now say Collapse All
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		// The "+X more" overflow indicator should be gone, replaced by "Show less"
		await expect(dayCell.locator('.calendar-overflow')).toContainText('Show less');

		// The 4th task should now be visible (not hidden)
		const visibleTasks = dayCell.locator('.calendar-task:not(.calendar-task-hidden)');
		await expect(visibleTasks).toHaveCount(4);
	});

	test('clicking collapse all hides overflowed tasks again', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Collapse Task ${i}`, { dueDate });
		}

		await page.reload();
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Expand, then collapse
		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');

		// Overflow indicator should be back
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more');
	});

	test('manually expanding all overflowing days syncs button to collapse all', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Sync Task ${i}`, { dueDate });
		}

		await page.reload();
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Button should say Expand All initially
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');

		// Manually expand the one overflowing day
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await dayCell.locator('.calendar-overflow').click();

		// Since all overflowing days are now expanded, button should say Collapse All
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');
	});

	test('week navigation resets expanded state', async ({ page }) => {
		for (let i = 1; i <= 4; i++) {
			await createTodoViaAPI(page, `Nav Task ${i}`, { dueDate });
		}

		await page.reload();
		await page.waitForSelector('#drag-drop-calendar', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Expand all
		await page.locator('.expand-all-btn').click();
		await expect(page.locator('.expand-all-btn')).toHaveText('Collapse All');

		// Navigate to next week and back
		await page.locator('button:has-text("Next")').click();
		await page.locator('button:has-text("Previous")').click();

		// After navigating back, expandedDays was reset so the overflow should be collapsed
		const dayCell = page.locator(`.calendar-day[data-date="${dueDate}"]`);
		await expect(dayCell.locator('.calendar-overflow')).toContainText('more');
		await expect(page.locator('.expand-all-btn')).toHaveText('Expand All');
	});
});
