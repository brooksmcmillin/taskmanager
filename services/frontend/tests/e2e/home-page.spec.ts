import { test, expect } from '@playwright/test';
import {
	registerAndLogin,
	createTodoViaAPI,
	getTodayDate,
	getPastDate
} from '../helpers/test-utils';

test.describe('Home Page', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('should display greeting and date', async ({ page }) => {
		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		const greeting = page.locator('.greeting');
		await expect(greeting).toBeVisible();
		// Should contain one of the time-of-day greetings
		const text = await greeting.textContent();
		expect(['Good morning', 'Good afternoon', 'Good evening']).toContain(text);

		await expect(page.locator('.date')).toBeVisible();
	});

	test('should display both panels', async ({ page }) => {
		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		// Both panel titles should be visible
		await expect(page.locator('.panel-title', { hasText: 'Due Today' })).toBeVisible();
		await expect(page.locator('.panel-title', { hasText: 'Feed' })).toBeVisible();
	});

	test('should show empty state when no tasks due today', async ({ page }) => {
		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		// New user should have no tasks, so empty state should show
		await expect(page.locator('.empty-state', { hasText: 'Nothing due today' })).toBeVisible();
	});

	test('should show task due today', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Home Page Test Task', { dueDate: today });

		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.task-title', { hasText: 'Home Page Test Task' })).toBeVisible();
		await expect(page.locator('.badge').first()).toHaveText('1');
	});

	test('should show overdue tasks in separate section', async ({ page }) => {
		const yesterday = getPastDate(1);
		await createTodoViaAPI(page, 'Overdue Home Task', { dueDate: yesterday });

		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		await expect(page.locator('.section-label.overdue', { hasText: 'Overdue' })).toBeVisible();
		await expect(page.locator('.task-title', { hasText: 'Overdue Home Task' })).toBeVisible();
	});

	test('should link tasks to detail page', async ({ page }) => {
		const today = getTodayDate();
		await createTodoViaAPI(page, 'Linked Task', { dueDate: today });

		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		const taskLink = page.locator('.task-item', { hasText: 'Linked Task' });
		const href = await taskLink.getAttribute('href');
		expect(href).toMatch(/^\/task\/\d+$/);
	});

	test('should show feed panel with empty or populated state', async ({ page }) => {
		await page.goto('/home');
		await page.waitForLoadState('networkidle');

		// Feed panel should resolve to either articles or empty state
		const feedPanel = page.locator('.panel').nth(1);
		const hasArticles = await feedPanel.locator('.article-item').count();
		const hasEmpty = await feedPanel.locator('.empty-state').count();
		expect(hasArticles + hasEmpty).toBeGreaterThan(0);
	});

	test('should redirect to login when not authenticated', async ({ page }) => {
		await page.context().clearCookies();
		await page.goto('/home');

		await expect(page).toHaveURL(/\/login/);
	});
});
