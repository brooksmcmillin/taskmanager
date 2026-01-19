import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
	webServer: [
		{
			// Reset and start backend with test database
			// Always start fresh to ensure clean database state
			command:
				'bash -c "set -a && source .env.test && set +a && uv run python scripts/reset_test_db.py && bash scripts/start_test_server.sh"',
			port: 8010,
			timeout: 120000,
			reuseExistingServer: false,
			cwd: '../backend'
		},
		{
			// Build and start frontend connected to test backend
			// Build with test mode, then run the Node adapter server with BACKEND_URL env var
			command:
				'npm run build -- --mode test && PORT=4173 BACKEND_URL=http://localhost:8010 node build',
			port: 4173,
			timeout: 120000,
			reuseExistingServer: false,
			cwd: '.'
		}
	],
	testDir: 'tests/e2e',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	use: {
		baseURL: 'http://localhost:4173',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		video: 'retain-on-failure',
		headless: true
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
		}
		// WebKit disabled - missing system dependencies on Debian
		// {
		// 	name: 'webkit',
		// 	use: {
		// 		browserName: 'webkit'
		// 	}
		// }
	]
};

export default config;
