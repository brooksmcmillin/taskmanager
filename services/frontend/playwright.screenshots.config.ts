import type { PlaywrightTestConfig } from '@playwright/test';

/**
 * Playwright configuration for README screenshot generation
 *
 * This config uses your running dev environment (https://localhost)
 * instead of spinning up test servers with a fresh database.
 *
 * Prerequisites:
 * - Frontend dev server running on https://localhost (npm run dev)
 * - Backend dev server running
 * - testuser account exists with sample data populated
 *
 * Usage:
 *   npx playwright test readme-screenshots.spec.ts --config=playwright.screenshots.config.ts --project=chromium
 */
const config: PlaywrightTestConfig = {
	testDir: 'tests/e2e',
	testMatch: /readme-screenshots\.spec\.ts/,
	use: {
		baseURL: 'https://localhost:3000',
		ignoreHTTPSErrors: true,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure',
		headless: true
	},
	reporter: [['list']],
	timeout: 30000,
	expect: {
		timeout: 5000
	},
	fullyParallel: false,
	retries: 0,
	workers: 1,
	projects: [
		{
			name: 'chromium',
			use: {
				browserName: 'chromium'
			}
		}
	]
};

export default config;
