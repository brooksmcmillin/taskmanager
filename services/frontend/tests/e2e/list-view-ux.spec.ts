/**
 * E2E Tests: List View UX Improvements
 *
 * Tests for priority color legend, CSS tooltips on action buttons,
 * consistent card info density, masonry layout, and Inbox label.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin, createTodoViaAPI, getFutureDate } from '../helpers/test-utils';

test.describe('Priority Color Legend', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should display priority legend in list view', async ({ page }) => {
		await createTodoViaAPI(page, 'Legend Test Task');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// Switch to list view
		await page.click('button:has-text("List View")');

		// Legend should be visible
		const legend = page.locator('.priority-legend');
		await expect(legend).toBeVisible({ timeout: 5000 });

		// All four priority levels should appear
		await expect(legend.locator('.legend-item', { hasText: 'Urgent' })).toBeVisible();
		await expect(legend.locator('.legend-item', { hasText: 'High' })).toBeVisible();
		await expect(legend.locator('.legend-item', { hasText: 'Medium' })).toBeVisible();
		await expect(legend.locator('.legend-item', { hasText: 'Low' })).toBeVisible();

		// Each legend item should have a colored dot
		const dots = legend.locator('.legend-dot');
		await expect(dots).toHaveCount(4);
	});

	test('should not display priority legend in calendar view', async ({ page }) => {
		await createTodoViaAPI(page, 'Calendar Legend Test');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// Default is calendar view — legend should not be visible
		await expect(page.locator('.priority-legend')).not.toBeVisible();
	});
});

test.describe('CSS Tooltips on Action Buttons', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should have data-tooltip and aria-label on action buttons', async ({ page }) => {
		await createTodoViaAPI(page, 'Tooltip Test Task');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Tooltip Test Task' });
		await expect(taskCard).toBeVisible({ timeout: 5000 });

		// Edit button should have data-tooltip and aria-label
		const editBtn = taskCard.locator('[data-tooltip="Edit todo"]');
		await expect(editBtn).toBeVisible();
		await expect(editBtn).toHaveAttribute('aria-label', 'Edit todo');

		// Complete button should have data-tooltip and aria-label
		const completeBtn = taskCard.locator('[data-tooltip="Mark as complete"]');
		await expect(completeBtn).toBeVisible();
		await expect(completeBtn).toHaveAttribute('aria-label', 'Mark as complete');
	});
});

test.describe('Task Card Info Density', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should show "No date" for tasks without a due date', async ({ page }) => {
		await createTodoViaAPI(page, 'No Date Task');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'No Date Task' });
		await expect(taskCard).toBeVisible({ timeout: 5000 });

		// Should display "No date" text
		await expect(taskCard.locator('text=No date')).toBeVisible();
	});

	test('should show formatted due date for tasks with a due date', async ({ page }) => {
		const dueDate = getFutureDate(3);
		await createTodoViaAPI(page, 'Dated Task', { dueDate });

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Dated Task' });
		await expect(taskCard).toBeVisible({ timeout: 5000 });

		// Should display "Due:" with a date, not "No date"
		await expect(taskCard.locator('text=Due:')).toBeVisible();
		await expect(taskCard.locator('text=No date')).not.toBeVisible();
	});

	test('should always show priority label', async ({ page }) => {
		await createTodoViaAPI(page, 'Priority Label Task', { priority: 'high' });

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		const taskCard = page.locator('.todo-with-subtasks', { hasText: 'Priority Label Task' });
		await expect(taskCard).toBeVisible({ timeout: 5000 });

		// Should show the priority text
		await expect(taskCard.locator('text=High')).toBeVisible();
	});
});

test.describe('Masonry Layout', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should use CSS columns layout for project cards', async ({ page }) => {
		await createTodoViaAPI(page, 'Layout Test Task');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		const todoLists = page.locator('#todo-lists');
		await expect(todoLists).toBeVisible({ timeout: 5000 });

		// Should not have grid classes
		const classAttr = await todoLists.getAttribute('class');
		expect(classAttr ?? '').not.toContain('grid');
	});
});

test.describe('Inbox Label', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should show "Inbox" for tasks with no project', async ({ page }) => {
		// Create task without a project
		await createTodoViaAPI(page, 'Unassigned Task');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		// Should show "Inbox" heading, not "No Project"
		await expect(page.locator('h3', { hasText: 'Inbox' })).toBeVisible({ timeout: 5000 });
		await expect(page.locator('h3', { hasText: 'No Project' })).not.toBeVisible();
	});

	test('should sort Inbox last among project groups', async ({ page }) => {
		// Create a project first
		const projectRes = await page.request.post('/api/projects', {
			data: { name: `AAA Project ${Date.now()}`, color: '#3b82f6' }
		});
		const projectData = await projectRes.json();
		const projectId = projectData.data?.id;

		// Create task in the project
		await createTodoViaAPI(page, 'Project Task');
		// Assign to project via API if possible
		if (projectId) {
			await page.request.post('/api/todos', {
				data: { title: 'AAA Project Task', project_id: projectId }
			});
		}

		// Create task without a project
		await createTodoViaAPI(page, 'Inbox Task No Project');

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		await page.click('button:has-text("List View")');

		// Wait for cards to render
		await expect(page.locator('.card').first()).toBeVisible({ timeout: 5000 });

		// Get all project headings
		const headings = page.locator('#todo-lists h3');
		const count = await headings.count();

		if (count > 1) {
			// Inbox should be the last heading
			const lastHeading = await headings.nth(count - 1).textContent();
			expect(lastHeading).toBe('Inbox');
		}
	});
});
