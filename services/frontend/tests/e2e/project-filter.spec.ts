/**
 * E2E Tests: Project Filter Persistence & Auto-set Project on New Tasks
 *
 * Tests for:
 * - #223: Auto-set project on new tasks when filter is active
 * - #224: Persist project filter selection across views and page refreshes
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin, createTodoViaAPI } from '../helpers/test-utils';

/**
 * Helper to create a project via API and return its ID and name.
 */
async function createProjectViaAPI(
	page: import('@playwright/test').Page,
	name: string,
	color: string = '#3b82f6'
): Promise<{ id: number; name: string }> {
	const response = await page.request.post('/api/projects', {
		data: { name, color }
	});
	if (!response.ok()) {
		throw new Error(`Failed to create project: ${response.status()} ${await response.text()}`);
	}
	const json = await response.json();
	return { id: json.data.id, name: json.data.name };
}

/**
 * Select a project in the filter dropdown and wait for the URL to update.
 */
async function selectProjectFilter(
	page: import('@playwright/test').Page,
	projectId: number
): Promise<void> {
	await page.locator('.project-filter-container select').selectOption(String(projectId));
	await page.waitForURL(/project_id/, { timeout: 5000 });
	await page.waitForLoadState('networkidle');
}

test.describe('Auto-set project on new tasks (#223)', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should pre-fill project when creating a task with project filter active', async ({
		page
	}) => {
		const project = await createProjectViaAPI(page, `Test Project ${Date.now()}`);
		await createTodoViaAPI(page, 'Existing Task');

		// Navigate to tasks page with project filter in URL
		await page.goto(`/?project_id=${project.id}`);
		await page.waitForLoadState('networkidle');

		// Open the create task panel
		await page.click('.add-todo-btn');

		// Wait for the form to appear
		await expect(page.locator('#project_id')).toBeVisible({ timeout: 5000 });

		// The project select should be pre-filled with the filtered project
		await expect(page.locator('#project_id')).toHaveValue(String(project.id));
	});

	test('should not pre-fill project when no filter is active', async ({ page }) => {
		await createProjectViaAPI(page, `Unfiltered Project ${Date.now()}`);

		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// Open the create task panel
		await page.click('.add-todo-btn');

		// Wait for the form to appear
		await expect(page.locator('#project_id')).toBeVisible({ timeout: 5000 });

		// The project select should be empty (no pre-fill)
		await expect(page.locator('#project_id')).toHaveValue('');
	});
});

test.describe('Persist project filter across views (#224)', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should persist project filter when navigating away and back', async ({ page }) => {
		const project = await createProjectViaAPI(page, `Persist Project ${Date.now()}`);

		// Navigate to tasks page and select the project filter
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await selectProjectFilter(page, project.id);

		// Navigate away to another page
		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		// Navigate back to tasks page (without project_id in URL)
		await page.goto('/');
		// Wait for the onMount redirect to restore the filter from localStorage
		await page.waitForURL(/project_id/, { timeout: 5000 });

		// The project filter dropdown should show the selected project
		await expect(page.locator('.project-filter-container select')).toHaveValue(String(project.id));
	});

	test('should persist project filter across page refresh', async ({ page }) => {
		const project = await createProjectViaAPI(page, `Refresh Project ${Date.now()}`);

		// Navigate and select the project filter to save to localStorage
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await selectProjectFilter(page, project.id);

		// Navigate to / without the query parameter (simulates refresh losing query params)
		await page.goto('/');
		// Wait for the onMount redirect to restore the filter
		await page.waitForURL(/project_id/, { timeout: 5000 });

		// Should restore from localStorage
		expect(page.url()).toContain(`project_id=${project.id}`);
	});

	test('should clear stale filter when project no longer exists', async ({ page }) => {
		const project = await createProjectViaAPI(page, `Stale Project ${Date.now()}`);

		// Set a project filter and persist it
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await selectProjectFilter(page, project.id);

		// Delete the project via API
		const deleteRes = await page.request.delete(`/api/projects/${project.id}`);
		expect(deleteRes.ok()).toBeTruthy();

		// Navigate away and back — stale filter should be cleared
		await page.goto('/home');
		await page.waitForLoadState('networkidle');
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// Filter should have been cleared since the project no longer exists
		expect(page.url()).not.toContain('project_id');
	});

	test('should clear persisted filter when "All Projects" is selected', async ({ page }) => {
		const project = await createProjectViaAPI(page, `Clear Project ${Date.now()}`);

		// Set a project filter and persist it
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await selectProjectFilter(page, project.id);

		// Clear the filter by selecting "All Projects" (empty value)
		await page.locator('.project-filter-container select').selectOption('');
		// Wait for URL to lose the project_id param
		await page.waitForURL((url) => !url.searchParams.has('project_id'), { timeout: 5000 });

		// Navigate away and back
		await page.goto('/home');
		await page.waitForLoadState('networkidle');
		await page.goto('/');
		await page.waitForLoadState('networkidle');

		// Filter should NOT be restored (was cleared)
		expect(page.url()).not.toContain('project_id');
	});
});
