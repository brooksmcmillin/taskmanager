/**
 * Test Utility Functions
 *
 * Helper functions for E2E tests to avoid hardcoded values and improve test reliability
 */

import type { Page } from '@playwright/test';

/**
 * Generate a future date N days from now
 * @param daysFromNow - Number of days in the future
 * @returns Date string in YYYY-MM-DD format
 */
export function getFutureDate(daysFromNow: number = 5): string {
	const date = new Date();
	date.setDate(date.getDate() + daysFromNow);
	return date.toISOString().split('T')[0];
}

/**
 * Generate a past date N days ago
 * @param daysAgo - Number of days in the past
 * @returns Date string in YYYY-MM-DD format
 */
export function getPastDate(daysAgo: number = 5): string {
	const date = new Date();
	date.setDate(date.getDate() - daysAgo);
	return date.toISOString().split('T')[0];
}

/**
 * Get today's date in YYYY-MM-DD format
 */
export function getTodayDate(): string {
	return new Date().toISOString().split('T')[0];
}

/**
 * Generate a unique email for testing
 * Avoids conflicts when tests create users
 */
export function getUniqueEmail(): string {
	return `testuser-${Date.now()}@example.com`;
}

/**
 * Wait for API response instead of using fixed timeout
 * @param page - Playwright page object
 * @param urlPattern - URL pattern to match (string or regex)
 * @param method - HTTP method (GET, POST, etc.)
 */
export async function waitForApiResponse(
	page: Page,
	urlPattern: string | RegExp,
	method: string = 'GET'
) {
	return await page.waitForResponse(
		(response) => {
			const url = response.url();
			const matchesUrl =
				typeof urlPattern === 'string' ? url.includes(urlPattern) : urlPattern.test(url);
			return matchesUrl && response.request().method() === method;
		},
		{ timeout: 10000 }
	);
}

/**
 * Wait for network to be idle (all requests complete)
 * More reliable than waitForTimeout
 */
export async function waitForNetworkIdle(page: Page) {
	await page.waitForLoadState('networkidle', { timeout: 10000 });
}

/**
 * Fill a date input with a dynamic future date
 * @param page - Playwright page object
 * @param selector - Input selector
 * @param daysFromNow - Number of days in the future
 */
export async function fillFutureDate(page: Page, selector: string, daysFromNow: number = 5) {
	const dateStr = getFutureDate(daysFromNow);
	await page.fill(selector, dateStr);
	return dateStr;
}

/**
 * Login helper to reduce code duplication
 * @param page - Playwright page object
 * @param email - Email (defaults to test@example.com)
 * @param password - Password (defaults to test password)
 */
export async function login(
	page: Page,
	email: string = 'test@example.com',
	password: string = 'TestPass123!' // pragma: allowlist secret
) {
	await page.goto('/login');
	await page.fill('[name=email]', email);
	await page.fill('[name=password]', password);
	await page.click('button[type=submit]');

	// Wait for successful redirect
	await page.waitForURL('/', { timeout: 10000 });
}

/**
 * Register and login helper - creates a new user and logs them in
 * Useful when test database is reset between runs
 * @param page - Playwright page object
 * @param email - Email (defaults to unique email with timestamp)
 * @param password - Password (defaults to test password)
 */
export async function registerAndLogin(
	page: Page,
	email?: string,
	password: string = 'TestPass123!' // pragma: allowlist secret
) {
	// Use unique email if not provided to avoid conflicts between tests
	const actualEmail = email ?? getUniqueEmail();

	// Register the user
	await page.goto('/register');
	await page.fill('[name=email]', actualEmail);
	await page.fill('[name=password]', password);
	await page.click('button[type=submit]');
	await page.waitForURL('/login', { timeout: 10000 });

	// Login
	await login(page, actualEmail, password);
}

/**
 * Create a todo via UI
 * @param page - Playwright page object
 * @param title - Todo title
 * @param options - Optional todo fields
 */
export async function createTodoViaUI(
	page: Page,
	title: string,
	options: {
		description?: string;
		priority?: string;
		dueDate?: string;
		projectId?: string;
	} = {}
) {
	await page.click('[data-testid=add-todo-button]');
	await page.waitForSelector('.modal', { state: 'visible' });

	await page.fill('[name=title]', title);

	if (options.description) {
		await page.fill('[name=description]', options.description);
	}

	if (options.priority) {
		await page.selectOption('[name=priority]', options.priority);
	}

	if (options.dueDate) {
		await page.fill('[name=due_date]', options.dueDate);
	}

	if (options.projectId) {
		await page.selectOption('[name=project_id]', options.projectId);
	}

	// Submit and wait for modal to close
	await page.click('[data-testid=save-todo]');
	await page.waitForSelector('.modal', { state: 'hidden', timeout: 5000 });

	// Wait for API response
	await waitForApiResponse(page, '/api/todos', 'POST');
}

/**
 * Cleanup helper - delete all todos created by a user
 * Useful in afterEach hooks
 */
export async function cleanupTodos(page: Page) {
	// This would require API access or UI cleanup
	// For now, document that database should be reset between test runs
	console.log('TODO: Implement todo cleanup');
}

/**
 * Generate test data for a todo
 */
export function generateTodoData(overrides: Partial<any> = {}) {
	return {
		title: `Test Task ${Date.now()}`,
		description: 'Test description',
		priority: 'medium',
		status: 'pending',
		due_date: getFutureDate(5),
		...overrides
	};
}

/**
 * Take a screenshot and save to docs/screenshots directory (at project root)
 * @param page - Playwright page object
 * @param name - Screenshot filename (without extension)
 * @param options - Screenshot options
 */
export async function takeScreenshot(
	page: Page,
	name: string,
	options: {
		fullPage?: boolean;
		clip?: { x: number; y: number; width: number; height: number };
	} = {}
) {
	// Path relative to services/frontend where tests run
	const screenshotsDir = '../../docs/screenshots';
	const path = `${screenshotsDir}/${name}.png`;

	await page.screenshot({
		path,
		fullPage: options.fullPage ?? false,
		clip: options.clip
	});

	return path;
}
