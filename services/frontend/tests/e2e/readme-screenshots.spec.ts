/**
 * Screenshot Generation for README
 *
 * This test file generates screenshots of key UI screens for documentation.
 * Run with: npx playwright test readme-screenshots.spec.ts --project=chromium
 *
 * Screenshots are saved to: docs/screenshots/
 */

import { test } from '@playwright/test';
import { registerAndLogin, takeScreenshot, waitForNetworkIdle } from '../helpers/test-utils';

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

		// Register and login to access the dashboard
		await registerAndLogin(page);
		await waitForNetworkIdle(page);

		await takeScreenshot(page, 'dashboard');
	});

	test('capture settings page', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });

		// Register and login first
		await registerAndLogin(page);
		await waitForNetworkIdle(page);

		// Navigate to settings
		await page.goto('/settings');
		await waitForNetworkIdle(page);

		await takeScreenshot(page, 'settings-page');
	});

	test('capture full dashboard (full page)', async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 720 });

		await registerAndLogin(page);
		await waitForNetworkIdle(page);

		await takeScreenshot(page, 'dashboard-full', { fullPage: true });
	});
});
