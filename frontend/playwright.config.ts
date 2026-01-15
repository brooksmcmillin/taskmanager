import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
	webServer: {
		command: 'npm run build && npm run preview',
		port: 4173,
		timeout: 120000,
		reuseExistingServer: !process.env.CI
	},
	testDir: 'tests/e2e',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	use: {
		baseURL: 'http://localhost:4173',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure'
	},
	reporter: [
		['html', { outputFolder: 'playwright-report' }],
		['list'],
		['json', { outputFile: 'test-results.json' }]
	],
	timeout: 30000,
	expect: {
		timeout: 5000
	},
	// Disable parallel execution until test isolation is fixed
	// (shared test data can cause race conditions)
	fullyParallel: false,
	forbidOnly: !!process.env.CI,
	retries: process.env.CI ? 2 : 0,
	workers: process.env.CI ? 1 : undefined,
	projects: [
		{
			name: 'chromium',
			use: {
				browserName: 'chromium'
			}
		},
		{
			name: 'firefox',
			use: {
				browserName: 'firefox'
			}
		},
		{
			name: 'webkit',
			use: {
				browserName: 'webkit'
			}
		}
	]
};

export default config;
