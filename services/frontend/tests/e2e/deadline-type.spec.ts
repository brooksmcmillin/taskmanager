/**
 * E2E Test: Deadline Type Feature
 *
 * Tests the deadline_type field in the todo form and API interactions.
 * Verifies create, edit, and default behavior for all deadline type values.
 */

import { test, expect } from '@playwright/test';
import { registerAndLogin, createTodoViaAPI, getFutureDate } from '../helpers/test-utils';

test.describe('Deadline Type Feature', () => {
	test.beforeEach(async ({ page }) => {
		await registerAndLogin(page);
	});

	test.describe('Form UI', () => {
		test('should display deadline_type select in create form', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Open create task panel
			await page.click('.add-todo-btn');

			// Wait for the panel to appear
			await page.waitForSelector('[name=deadline_type]', { state: 'visible' });

			// Verify the select element exists with correct options
			const select = page.locator('[name=deadline_type]');
			await expect(select).toBeVisible();

			const options = select.locator('option');
			await expect(options).toHaveCount(4);
			await expect(options.nth(0)).toHaveText('Flexible');
			await expect(options.nth(1)).toHaveText('Preferred');
			await expect(options.nth(2)).toHaveText('Firm');
			await expect(options.nth(3)).toHaveText('Hard');
		});

		test('should default to preferred deadline type', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Open create task panel
			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=deadline_type]', { state: 'visible' });

			const select = page.locator('[name=deadline_type]');
			await expect(select).toHaveValue('preferred');
		});

		test('should allow selecting each deadline type value', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Open create task panel
			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=deadline_type]', { state: 'visible' });

			const select = page.locator('[name=deadline_type]');

			for (const value of ['flexible', 'preferred', 'firm', 'hard']) {
				await select.selectOption(value);
				await expect(select).toHaveValue(value);
			}
		});
	});

	test.describe('Create with deadline type', () => {
		test('should create todo with default preferred deadline type', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Open create task panel
			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=title]', { state: 'visible' });

			// Fill title only (deadline_type should default to preferred)
			await page.fill('[name=title]', 'Default Deadline Task');

			// Submit
			await page.click('button[type=submit]');

			// Wait for the panel to close (form dispatches success which closes panel)
			await page.waitForTimeout(500);

			// Verify the todo was created via API
			const response = await page.request.get('/api/todos');
			const data = await response.json();
			const todos = data.data || data;
			const created = todos.find((t: { title: string }) => t.title === 'Default Deadline Task');
			expect(created).toBeTruthy();
			expect(created.deadline_type).toBe('preferred');
		});

		test('should create todo with hard deadline type', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Open create task panel
			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=title]', { state: 'visible' });

			// Fill form with hard deadline type
			await page.fill('[name=title]', 'Hard Deadline Task');
			await page.fill('[name=due_date]', getFutureDate(7));
			await page.selectOption('[name=deadline_type]', 'hard');

			// Submit
			await page.click('button[type=submit]');
			await page.waitForTimeout(500);

			// Verify via API
			const response = await page.request.get('/api/todos');
			const data = await response.json();
			const todos = data.data || data;
			const created = todos.find((t: { title: string }) => t.title === 'Hard Deadline Task');
			expect(created).toBeTruthy();
			expect(created.deadline_type).toBe('hard');
		});

		test('should create todo with flexible deadline type', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=title]', { state: 'visible' });

			await page.fill('[name=title]', 'Flexible Deadline Task');
			await page.selectOption('[name=deadline_type]', 'flexible');

			await page.click('button[type=submit]');
			await page.waitForTimeout(500);

			const response = await page.request.get('/api/todos');
			const data = await response.json();
			const todos = data.data || data;
			const created = todos.find((t: { title: string }) => t.title === 'Flexible Deadline Task');
			expect(created).toBeTruthy();
			expect(created.deadline_type).toBe('flexible');
		});

		test('should create todo with firm deadline type', async ({ page }) => {
			await page.goto('/');
			await page.waitForLoadState('networkidle');

			await page.click('.add-todo-btn');
			await page.waitForSelector('[name=title]', { state: 'visible' });

			await page.fill('[name=title]', 'Firm Deadline Task');
			await page.selectOption('[name=deadline_type]', 'firm');

			await page.click('button[type=submit]');
			await page.waitForTimeout(500);

			const response = await page.request.get('/api/todos');
			const data = await response.json();
			const todos = data.data || data;
			const created = todos.find((t: { title: string }) => t.title === 'Firm Deadline Task');
			expect(created).toBeTruthy();
			expect(created.deadline_type).toBe('firm');
		});
	});

	test.describe('Edit deadline type', () => {
		test('should populate deadline_type when editing a todo', async ({ page }) => {
			// Create a todo with hard deadline via API
			await createTodoViaAPI(page, 'Edit DL Type Task', {
				deadlineType: 'hard',
				dueDate: getFutureDate(5)
			});

			// Navigate to task detail page
			const listResponse = await page.request.get('/api/todos');
			const listData = await listResponse.json();
			const todos = listData.data || listData;
			const todo = todos.find((t: { title: string }) => t.title === 'Edit DL Type Task');
			expect(todo).toBeTruthy();

			await page.goto(`/task/${todo.id}`);
			await page.waitForLoadState('networkidle');

			// Click Edit Task button
			await page.click('button:has-text("Edit Task")');
			await page.waitForSelector('[name=deadline_type]', { state: 'visible' });

			// Verify the deadline_type is pre-populated with 'hard'
			const select = page.locator('[name=deadline_type]');
			await expect(select).toHaveValue('hard');
		});

		test('should update deadline_type from hard to flexible', async ({ page }) => {
			// Create a todo with hard deadline via API
			await createTodoViaAPI(page, 'Update DL Task', {
				deadlineType: 'hard',
				dueDate: getFutureDate(5)
			});

			// Navigate to task detail page
			const listResponse = await page.request.get('/api/todos');
			const listData = await listResponse.json();
			const todos = listData.data || listData;
			const todo = todos.find((t: { title: string }) => t.title === 'Update DL Task');

			await page.goto(`/task/${todo.id}`);
			await page.waitForLoadState('networkidle');

			// Click Edit Task button
			await page.click('button:has-text("Edit Task")');
			await page.waitForSelector('[name=deadline_type]', { state: 'visible' });

			// Change deadline_type to flexible
			await page.selectOption('[name=deadline_type]', 'flexible');

			// Submit and wait for form to close (returns to view mode)
			await page.click('button[type=submit]');
			await expect(page.locator('button:has-text("Edit Task")')).toBeVisible({
				timeout: 10000
			});
			await page.waitForLoadState('networkidle');

			// Verify via API that deadline_type was updated
			const response = await page.request.get(`/api/todos/${todo.id}`);
			const data = await response.json();
			const updated = data.data || data;
			expect(updated.deadline_type).toBe('flexible');
		});
	});

	test.describe('Display in views', () => {
		test('should show deadline type badge in task detail page', async ({ page }) => {
			await createTodoViaAPI(page, 'Detail Badge Task', {
				deadlineType: 'hard',
				dueDate: getFutureDate(5)
			});

			const listResponse = await page.request.get('/api/todos');
			const listData = await listResponse.json();
			const todos = listData.data || listData;
			const todo = todos.find((t: { title: string }) => t.title === 'Detail Badge Task');

			await page.goto(`/task/${todo.id}`);
			await page.waitForLoadState('networkidle');

			const badge = page.locator('.deadline-type-badge');
			await expect(badge).toBeVisible();
			await expect(badge).toHaveText('Hard');
		});

		test('should show pill for non-preferred deadline type in list view', async ({ page }) => {
			await createTodoViaAPI(page, 'Firm List Task', {
				deadlineType: 'firm',
				dueDate: getFutureDate(5)
			});

			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Switch to list view
			await page.click('button:has-text("List View")');

			const taskRow = page.locator('.todo-with-subtasks', {
				has: page.locator('text=Firm List Task')
			});
			await expect(taskRow.locator('.deadline-type-pill')).toBeVisible();
			await expect(taskRow.locator('.deadline-type-pill')).toHaveText('Firm');
		});

		test('should NOT show pill for preferred (default) deadline type in list view', async ({
			page
		}) => {
			await createTodoViaAPI(page, 'Preferred List Task', {
				deadlineType: 'preferred',
				dueDate: getFutureDate(5)
			});

			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Switch to list view
			await page.click('button:has-text("List View")');

			// Find the task row, verify no pill inside it
			const taskRow = page.locator('.todo-with-subtasks', {
				has: page.locator('text=Preferred List Task')
			});
			await expect(taskRow).toBeVisible();
			await expect(taskRow.locator('.deadline-type-pill')).toHaveCount(0);
		});

		test('should show deadline type label on calendar for non-preferred tasks', async ({
			page
		}) => {
			await createTodoViaAPI(page, 'Hard Calendar Task', {
				deadlineType: 'hard',
				dueDate: getFutureDate(3)
			});

			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Calendar is the default view — scope to the specific task card
			const taskCard = page.locator('.calendar-task', {
				has: page.locator('text=Hard Calendar Task')
			});
			await expect(taskCard.locator('.calendar-deadline-type')).toBeVisible();
			await expect(taskCard.locator('.calendar-deadline-type')).toHaveText('Hard');
		});

		test('should NOT show deadline type label on calendar for preferred tasks', async ({
			page
		}) => {
			await createTodoViaAPI(page, 'Preferred Calendar Task', {
				deadlineType: 'preferred',
				dueDate: getFutureDate(3)
			});

			await page.goto('/');
			await page.waitForLoadState('networkidle');

			// Find the calendar task card, verify no deadline label inside it
			const taskCard = page.locator('.calendar-task', {
				has: page.locator('text=Preferred Calendar Task')
			});
			await expect(taskCard).toBeVisible();
			await expect(taskCard.locator('.calendar-deadline-type')).toHaveCount(0);
		});

		test('should show pill for flexible deadline type in home dashboard', async ({ page }) => {
			const d = new Date();
			const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
			await createTodoViaAPI(page, 'Flexible Home Task', {
				deadlineType: 'flexible',
				dueDate: today
			});

			await page.goto('/home');
			await page.waitForLoadState('networkidle');

			const taskItem = page.locator('.task-item', {
				has: page.locator('text=Flexible Home Task')
			});
			await expect(taskItem.locator('.deadline-type-pill')).toBeVisible();
			await expect(taskItem.locator('.deadline-type-pill')).toHaveText('Flexible');
		});
	});

	test.describe('API deadline type', () => {
		test('should create todo with each valid deadline_type via API', async ({ page }) => {
			const deadlineTypes = ['flexible', 'preferred', 'firm', 'hard'];

			for (const dt of deadlineTypes) {
				const result = await createTodoViaAPI(page, `API ${dt} task`, {
					deadlineType: dt,
					dueDate: getFutureDate(5)
				});
				const todo = result.data || result;
				expect(todo.deadline_type).toBe(dt);
			}
		});

		test('should default deadline_type to preferred when not specified', async ({ page }) => {
			const result = await createTodoViaAPI(page, 'API default DL task');
			const todo = result.data || result;
			expect(todo.deadline_type).toBe('preferred');
		});

		test('should persist deadline_type through update', async ({ page }) => {
			// Create with firm
			const createResult = await createTodoViaAPI(page, 'API persist DL task', {
				deadlineType: 'firm'
			});
			const created = createResult.data || createResult;
			expect(created.deadline_type).toBe('firm');

			// Update to hard
			const updateResponse = await page.request.put(`/api/todos/${created.id}`, {
				data: { deadline_type: 'hard' }
			});
			expect(updateResponse.ok()).toBeTruthy();
			const updateResult = await updateResponse.json();
			const updated = updateResult.data || updateResult;
			expect(updated.deadline_type).toBe('hard');

			// Fetch and verify
			const getResponse = await page.request.get(`/api/todos/${created.id}`);
			const getResult = await getResponse.json();
			const fetched = getResult.data || getResult;
			expect(fetched.deadline_type).toBe('hard');
		});
	});
});
