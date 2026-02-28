import { test, expect } from '@playwright/test';
import { registerAndLogin, createSnippetViaAPI, waitForNetworkIdle } from '../helpers/test-utils';

test.describe('Snippets', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('list page shows empty state', async ({ page }) => {
		await page.goto('/snippets');
		await waitForNetworkIdle(page);

		await expect(page.locator('.empty-state', { hasText: 'No snippets yet' })).toBeVisible();
	});

	test('list page shows created snippets', async ({ page }) => {
		await createSnippetViaAPI(page, 'Car', 'Oil change');
		await createSnippetViaAPI(page, 'House', 'HVAC filter');

		await page.goto('/snippets');
		await waitForNetworkIdle(page);

		await expect(page.locator('.snippet-title', { hasText: 'Oil change' })).toBeVisible();
		await expect(page.locator('.snippet-title', { hasText: 'HVAC filter' })).toBeVisible();
	});

	test('list page search filters results', async ({ page }) => {
		await createSnippetViaAPI(page, 'Car', 'Oil change');
		await createSnippetViaAPI(page, 'House', 'HVAC filter replacement');

		await page.goto('/snippets');
		await waitForNetworkIdle(page);

		await page.fill('.search-input', 'HVAC');
		// Wait for debounced search
		await page.waitForTimeout(400);
		await waitForNetworkIdle(page);

		await expect(
			page.locator('.snippet-title', { hasText: 'HVAC filter replacement' })
		).toBeVisible();
		await expect(page.locator('.snippet-title', { hasText: 'Oil change' })).not.toBeVisible();
	});

	test('create snippet via form', async ({ page }) => {
		await page.goto('/snippets/new');
		await waitForNetworkIdle(page);

		await page.fill('#category', 'Car Maintenance');
		await page.fill('#title', 'Changed air filter');
		await page.fill('#content', 'K&N filter model 33-2304');
		await page.fill('#tags', 'car, filter');
		await page.click('button[type=submit]');

		// Should redirect to the snippet view page
		await page.waitForURL(/\/snippets\/\d+/, { timeout: 10000 });
		await waitForNetworkIdle(page);

		await expect(
			page.locator('.detail-header h1', { hasText: 'Changed air filter' })
		).toBeVisible();
		await expect(page.locator('.snippet-category', { hasText: 'Car Maintenance' })).toBeVisible();
		await expect(page.locator('.detail-content')).toContainText('K&N filter model 33-2304');
	});

	test('view snippet by id', async ({ page }) => {
		const snippet = await createSnippetViaAPI(page, 'House', 'Replaced smoke detector battery', {
			content: 'Used Duracell 9V'
		});

		await page.goto(`/snippets/${snippet.id}`);
		await waitForNetworkIdle(page);

		await expect(
			page.locator('.detail-header h1', { hasText: 'Replaced smoke detector battery' })
		).toBeVisible();
		await expect(page.locator('.snippet-category', { hasText: 'House' })).toBeVisible();
		await expect(page.locator('.detail-content')).toContainText('Used Duracell 9V');
	});

	test('view snippet shows not-found state', async ({ page }) => {
		await page.goto('/snippets/99999');
		await waitForNetworkIdle(page);

		await expect(page.locator('.error-state')).toBeVisible();
	});

	test('edit snippet', async ({ page }) => {
		const snippet = await createSnippetViaAPI(page, 'Car', 'Oil change');

		await page.goto(`/snippets/${snippet.id}/edit`);
		await waitForNetworkIdle(page);

		await page.fill('#title', 'Oil change - synthetic');
		await page.fill('#content', '5W-30 Mobil 1');
		await page.click('button[type=submit]');

		// Should redirect back to the view page
		await page.waitForURL(new RegExp(`/snippets/${snippet.id}$`), { timeout: 10000 });
		await waitForNetworkIdle(page);

		await expect(
			page.locator('.detail-header h1', { hasText: 'Oil change - synthetic' })
		).toBeVisible();
		await expect(page.locator('.detail-content')).toContainText('5W-30 Mobil 1');
	});

	test('delete snippet', async ({ page }) => {
		const snippet = await createSnippetViaAPI(page, 'House', 'Delete me');

		await page.goto(`/snippets/${snippet.id}`);
		await waitForNetworkIdle(page);

		// Click delete (first click shows confirmation)
		await page.click('button:has-text("Delete")');
		// Confirm deletion
		await page.click('button:has-text("Confirm Delete")');

		// Should redirect to snippets list
		await page.waitForURL('/snippets', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Deleted snippet should not appear
		await expect(page.locator('.snippet-title', { hasText: 'Delete me' })).not.toBeVisible();
	});

	test('category filter chips', async ({ page }) => {
		await createSnippetViaAPI(page, 'Car', 'Oil change');
		await createSnippetViaAPI(page, 'House', 'HVAC filter');

		await page.goto('/snippets');
		await waitForNetworkIdle(page);

		// Category chips should appear
		await expect(page.locator('.category-chip', { hasText: 'Car' })).toBeVisible();
		await expect(page.locator('.category-chip', { hasText: 'House' })).toBeVisible();

		// Click Car category to filter
		await page.click('.category-chip:has-text("Car")');
		await waitForNetworkIdle(page);

		await expect(page.locator('.snippet-title', { hasText: 'Oil change' })).toBeVisible();
		await expect(page.locator('.snippet-title', { hasText: 'HVAC filter' })).not.toBeVisible();
	});

	test('tags displayed on view page', async ({ page }) => {
		const snippet = await createSnippetViaAPI(page, 'Car', 'Oil change', {
			tags: ['maintenance', 'oil']
		});

		await page.goto(`/snippets/${snippet.id}`);
		await waitForNetworkIdle(page);

		await expect(page.locator('.tag-chip', { hasText: 'maintenance' })).toBeVisible();
		await expect(page.locator('.tag-chip', { hasText: 'oil' })).toBeVisible();
	});

	test('create page with category query param', async ({ page }) => {
		await page.goto('/snippets/new?category=Car%20Maintenance');
		await waitForNetworkIdle(page);

		const categoryInput = page.locator('#category');
		await expect(categoryInput).toHaveValue('Car Maintenance');
	});
});
