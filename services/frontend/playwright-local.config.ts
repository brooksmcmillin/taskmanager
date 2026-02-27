import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
	testDir: 'tests/e2e',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	use: {
		baseURL: 'http://localhost:4173',
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure',
		headless: true
	},
	reporter: [['list']],
	timeout: 30000,
	expect: { timeout: 5000 },
	fullyParallel: false,
	retries: 0,
	projects: [
		{
			name: 'chromium',
			use: { browserName: 'chromium' }
		}
	]
};

export default config;
