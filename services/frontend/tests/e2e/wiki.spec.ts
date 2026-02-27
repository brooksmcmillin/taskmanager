import { test, expect } from '@playwright/test';
import { registerAndLogin, createWikiPageViaAPI, waitForNetworkIdle } from '../helpers/test-utils';

test.describe('Wiki Pages', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test('list page shows created pages', async ({ page }) => {
		await createWikiPageViaAPI(page, 'Alpha Page');
		await createWikiPageViaAPI(page, 'Beta Page');

		await page.goto('/wiki');
		await waitForNetworkIdle(page);

		await expect(page.locator('.node-title', { hasText: 'Alpha Page' })).toBeVisible();
		await expect(page.locator('.node-title', { hasText: 'Beta Page' })).toBeVisible();
	});

	test('list page search filters results', async ({ page }) => {
		await createWikiPageViaAPI(page, 'JavaScript Guide', 'Learn JS');
		await createWikiPageViaAPI(page, 'Python Guide', 'Learn Python');

		await page.goto('/wiki');
		await waitForNetworkIdle(page);

		await page.fill('.search-input', 'JavaScript');
		// Wait for debounced search
		await page.waitForTimeout(400);
		await waitForNetworkIdle(page);

		await expect(page.locator('.page-title', { hasText: 'JavaScript Guide' })).toBeVisible();
		await expect(page.locator('.page-title', { hasText: 'Python Guide' })).not.toBeVisible();
	});

	test('list page shows empty state', async ({ page }) => {
		await page.goto('/wiki');
		await waitForNetworkIdle(page);

		await expect(page.locator('.empty-state', { hasText: 'No wiki pages yet' })).toBeVisible();
	});

	test('create page via form', async ({ page }) => {
		await page.goto('/wiki/new');
		await waitForNetworkIdle(page);

		await page.fill('#title', 'My New Page');
		await page.fill('#content', '# Hello World\n\nSome content here.');
		await page.click('button[type=submit]');

		// Should redirect to the view page
		await page.waitForURL(/\/wiki\/my-new-page/, { timeout: 10000 });
		await waitForNetworkIdle(page);

		await expect(page.locator('.page-header h1', { hasText: 'My New Page' })).toBeVisible();
	});

	test('create page with title query param', async ({ page }) => {
		await page.goto('/wiki/new?title=Prefilled%20Title');
		await waitForNetworkIdle(page);

		const titleInput = page.locator('#title');
		await expect(titleInput).toHaveValue('Prefilled Title');
	});

	test('view page by slug', async ({ page }) => {
		await createWikiPageViaAPI(page, 'View Test Page', '# Content\n\nHello there.');

		await page.goto('/wiki/view-test-page');
		await waitForNetworkIdle(page);

		await expect(page.locator('.page-header h1', { hasText: 'View Test Page' })).toBeVisible();
		await expect(page.locator('.page-content')).toContainText('Hello there.');
	});

	test('view page shows not-found state', async ({ page }) => {
		await page.goto('/wiki/nonexistent-page-slug');
		await waitForNetworkIdle(page);

		await expect(page.locator('.error-state', { hasText: 'Page not found' })).toBeVisible();
	});

	test('edit page', async ({ page }) => {
		const wikiPage = await createWikiPageViaAPI(page, 'Edit Me', 'Original content');

		await page.goto(`/wiki/${wikiPage.slug}/edit`);
		await waitForNetworkIdle(page);

		await page.fill('#title', 'Edited Title');
		await page.fill('#content', 'Updated content here.');
		await page.click('button[type=submit]');

		// Should redirect to the updated page
		await page.waitForURL(/\/wiki\/edited-title/, { timeout: 10000 });
		await waitForNetworkIdle(page);

		await expect(page.locator('.page-header h1', { hasText: 'Edited Title' })).toBeVisible();
		await expect(page.locator('.page-content')).toContainText('Updated content here.');
	});

	test('delete page', async ({ page }) => {
		const wikiPage = await createWikiPageViaAPI(page, 'Delete Me');

		await page.goto(`/wiki/${wikiPage.slug}`);
		await waitForNetworkIdle(page);

		// Click the delete button (first click shows confirmation)
		await page.click('button:has-text("Delete")');
		// Confirm deletion
		await page.click('button:has-text("Confirm Delete")');

		// Should redirect to wiki list
		await page.waitForURL('/wiki', { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Deleted page should not appear
		await expect(page.locator('.node-title', { hasText: 'Delete Me' })).not.toBeVisible();
	});

	test('wiki links render as links', async ({ page }) => {
		// Create the target page first
		await createWikiPageViaAPI(page, 'Target Page', 'Target content');
		// Create a page with a wiki link
		await createWikiPageViaAPI(page, 'Source Page', 'See [[Target Page]] for details.');

		await page.goto('/wiki/source-page');
		await waitForNetworkIdle(page);

		const wikiLink = page.locator('.wiki-link');
		await expect(wikiLink).toBeVisible();
		await expect(wikiLink).toHaveAttribute('href', '/wiki/target-page');
	});

	test('create page with parent', async ({ page }) => {
		const parentPage = await createWikiPageViaAPI(page, 'Parent Page');

		// Use query param to set parent
		await page.goto(`/wiki/new?parent=${parentPage.id}`);
		await waitForNetworkIdle(page);

		await page.fill('#title', 'Child Page');
		await page.click('button[type=submit]');

		await page.waitForURL(/\/wiki\/child-page/, { timeout: 10000 });
		await waitForNetworkIdle(page);

		// Should show breadcrumbs with parent
		await expect(page.locator('.breadcrumb-link', { hasText: 'Parent Page' })).toBeVisible();
	});

	test('breadcrumb navigation', async ({ page }) => {
		const parentPage = await createWikiPageViaAPI(page, 'Breadcrumb Parent');

		// Create child via API with parent_id
		const childResponse = await page.request.post('/api/wiki', {
			data: { title: 'Breadcrumb Child', parent_id: parentPage.id }
		});
		const childPage = (await childResponse.json()).data;

		await page.goto(`/wiki/${childPage.slug}`);
		await waitForNetworkIdle(page);

		// Breadcrumb should show Wiki > Parent > Current
		await expect(page.locator('.breadcrumb-link', { hasText: 'Wiki' })).toBeVisible();
		await expect(page.locator('.breadcrumb-link', { hasText: 'Breadcrumb Parent' })).toBeVisible();
		await expect(
			page.locator('.breadcrumb-current', { hasText: 'Breadcrumb Child' })
		).toBeVisible();
	});

	test('child pages section on view page', async ({ page }) => {
		const parentPage = await createWikiPageViaAPI(page, 'Pages Parent');

		// Create child via API
		await page.request.post('/api/wiki', {
			data: { title: 'Sub Page One', parent_id: parentPage.id }
		});

		await page.goto(`/wiki/${parentPage.slug}`);
		await waitForNetworkIdle(page);

		// Should show child pages section
		await expect(page.locator('.linked-item', { hasText: 'Sub Page One' })).toBeVisible();
	});

	test('tags displayed on view page', async ({ page }) => {
		// Create page with tags via API
		await page.request.post('/api/wiki', {
			data: { title: 'Tagged Page', tags: ['design', 'ux'] }
		});

		await page.goto('/wiki/tagged-page');
		await waitForNetworkIdle(page);

		await expect(page.locator('.tag-chip', { hasText: 'design' })).toBeVisible();
		await expect(page.locator('.tag-chip', { hasText: 'ux' })).toBeVisible();
	});

	test('tag filter chips on list page', async ({ page }) => {
		await page.request.post('/api/wiki', {
			data: { title: 'Tag Filter A', tags: ['python'] }
		});
		await page.request.post('/api/wiki', {
			data: { title: 'Tag Filter B', tags: ['rust'] }
		});

		await page.goto('/wiki');
		await waitForNetworkIdle(page);

		// Both tag chips should appear
		await expect(page.locator('.tag-chip', { hasText: 'python' })).toBeVisible();
		await expect(page.locator('.tag-chip', { hasText: 'rust' })).toBeVisible();

		// Click python tag to filter
		await page.click('.tag-chip:has-text("python")');
		await waitForNetworkIdle(page);

		// Should show only python-tagged page (flat list mode)
		await expect(page.locator('.page-title', { hasText: 'Tag Filter A' })).toBeVisible();
		await expect(page.locator('.page-title', { hasText: 'Tag Filter B' })).not.toBeVisible();
	});
});
