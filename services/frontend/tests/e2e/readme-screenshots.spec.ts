/**
 * Screenshot Generation for README
 *
 * This test file generates screenshots of key UI screens for documentation.
 *
 * Prerequisites:
 * - Frontend dev server running on https://localhost (npm run dev)
 * - Backend dev server running
 * - testuser account (testuser/TestPass123!) exists with sample data
 *
 * Run with:
 *   npx playwright test readme-screenshots.spec.ts --config=playwright.screenshots.config.ts --project=chromium
 *
 * Screenshots are saved to: docs/screenshots/
 */

import { test, expect } from '@playwright/test';
import { login, takeScreenshot, waitForNetworkIdle } from '../helpers/test-utils';

test.describe('README Screenshots', () => {
	test.describe.configure({ mode: 'serial' });

	test('capture login page', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/login');

		await takeScreenshot(page, 'login-page');
	});

	test('capture registration page', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });
		await page.goto('/register');

		await takeScreenshot(page, 'register-page');
	});

	test('capture dashboard with tasks', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });

		// Login with pre-existing testuser account
		try {
			await login(page);
			await waitForNetworkIdle(page);
		} catch (error) {
			throw new Error(
				'Failed to login with testuser account. ' +
					'Ensure the testuser (testuser/TestPass123!) exists with sample data populated. ' +
					`Original error: ${error}`
			);
		}

		// Verify we're on the dashboard
		await expect(page).toHaveURL('/', { timeout: 5000 });

		await takeScreenshot(page, 'dashboard');
	});

	test('capture settings page', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });

		// Login with pre-existing testuser account
		try {
			await login(page);
			await waitForNetworkIdle(page);
		} catch (error) {
			throw new Error(
				'Failed to login with testuser account. ' +
					'Ensure the testuser (testuser/TestPass123!) exists with sample data populated. ' +
					`Original error: ${error}`
			);
		}

		// Navigate to settings
		await page.goto('/settings');
		await waitForNetworkIdle(page);

		await takeScreenshot(page, 'settings-page');
	});

	test('capture full dashboard (full page)', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });

		// Login with pre-existing testuser account
		try {
			await login(page);
			await waitForNetworkIdle(page);
		} catch (error) {
			throw new Error(
				'Failed to login with testuser account. ' +
					'Ensure the testuser (testuser/TestPass123!) exists with sample data populated. ' +
					`Original error: ${error}`
			);
		}

		await takeScreenshot(page, 'dashboard-full', { fullPage: true });
	});
});
