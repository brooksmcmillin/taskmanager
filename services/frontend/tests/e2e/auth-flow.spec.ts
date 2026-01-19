/**
 * E2E Test: Authentication Flow
 *
 * ⚠️ Status: Test Specification - Not Yet Executable
 * These tests serve as specifications for authentication functionality.
 * They will become executable once login/register pages are implemented.
 *
 * Tests user registration, login, and logout functionality
 */

import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
	test.beforeEach(async ({ page }) => {
		// Clear cookies before each test
		await page.context().clearCookies();
	});

	test('should register a new user', async ({ page }) => {
		await page.goto('/register');

		// Fill registration form with unique username to avoid conflicts
		const timestamp = Date.now();
		await page.fill('[name=username]', `testuser${timestamp}`);
		await page.fill('[name=email]', `test${timestamp}@example.com`);
		await page.fill('[name=password]', 'TestPass123!');

		// Submit form
		await page.click('button[type=submit]');

		// Wait for navigation
		await page.waitForURL('/login', { timeout: 10000 });

		// Should redirect to login page after successful registration
		await expect(page).toHaveURL('/login');
		await expect(page.locator('main h1')).toContainText('Login');
	});

	test('should login with valid credentials', async ({ page }) => {
		// Register a test user first
		await page.goto('/register');
		await page.fill('[name=username]', 'loginuser');
		await page.fill('[name=email]', 'loginuser@example.com');
		await page.fill('[name=password]', 'TestPass123!');
		await page.click('button[type=submit]');
		await page.waitForURL('/login', { timeout: 10000 });

		// Fill login form
		await page.fill('[name=username]', 'loginuser');
		await page.fill('[name=password]', 'TestPass123!');

		// Submit form
		await page.click('button[type=submit]');

		// Should redirect to dashboard
		await page.waitForURL('/', { timeout: 10000 });

		// Should see navigation bar with user info
		await expect(page.locator('.nav-bar')).toBeVisible();
	});

	test('should show error with invalid credentials', async ({ page }) => {
		await page.goto('/login');

		// Fill with invalid credentials
		await page.fill('[name=username]', 'nonexistent');
		await page.fill('[name=password]', 'wrongpass');

		// Submit form
		await page.click('button[type=submit]');

		// Should stay on login page and show error
		await expect(page).toHaveURL('/login');
		await expect(page.locator('.error-message')).toContainText('Invalid username or password');
	});

	test('should logout successfully', async ({ page }) => {
		// Register a test user first
		await page.goto('/register');
		await page.fill('[name=username]', 'logoutuser');
		await page.fill('[name=email]', 'logout@example.com');
		await page.fill('[name=password]', 'TestPass123!');
		await page.click('button[type=submit]');
		await page.waitForURL('/login', { timeout: 10000 });

		// Login
		await page.fill('[name=username]', 'logoutuser');
		await page.fill('[name=password]', 'TestPass123!');
		await page.click('button[type=submit]');

		// Wait for navigation to load with user data and logout button to appear
		await page.waitForSelector('[data-testid=logout-button]', { timeout: 10000 });

		// Click logout button
		await page.click('[data-testid=logout-button]');

		// Should redirect to login page
		await expect(page).toHaveURL('/login');

		// Verify session cookie is cleared
		const cookies = await page.context().cookies();
		const sessionCookie = cookies.find((c) => c.name === 'session');
		expect(sessionCookie).toBeUndefined();
	});

	test('should validate registration form fields', async ({ page }) => {
		await page.goto('/register');

		// Try to submit empty form
		await page.click('button[type=submit]');

		// Should show validation errors
		await expect(page.locator('[data-error=username]')).toBeVisible();
		await expect(page.locator('[data-error=email]')).toBeVisible();
		await expect(page.locator('[data-error=password]')).toBeVisible();

		// Test password strength validation
		await page.fill('[name=password]', 'weak');
		await page.locator('[name=password]').blur();
		await expect(page.locator('[data-error=password]')).toContainText(
			'Password must contain at least 2 of: lowercase, uppercase, numbers, special chars'
		);
	});

	test('should redirect to login when accessing protected page without auth', async ({ page }) => {
		await page.goto('/');

		// Should redirect to login page
		await expect(page).toHaveURL('/login');
	});
});
