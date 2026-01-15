/**
 * E2E Test: Todo Management Flow
 *
 * Tests creating, editing, completing, and deleting todos
 */

import { test, expect } from '@playwright/test';

test.describe('Todo Management Flow', () => {
	test.beforeEach(async ({ page }) => {
		// Login before each test
		await page.goto('/login');
		await page.fill('[name=username]', 'testuser');
		await page.fill('[name=password]', 'TestPass123!');
		await page.click('button[type=submit]');
		await expect(page).toHaveURL('/');
	});

	test('should create a new todo', async ({ page }) => {
		// Click add todo button
		await page.click('[data-testid=add-todo-button]');

		// Wait for modal to appear
		await expect(page.locator('.modal')).toBeVisible();

		// Fill todo form
		await page.fill('[name=title]', 'Test Task');
		await page.fill('[name=description]', 'This is a test task');
		await page.selectOption('[name=priority]', 'high');
		await page.selectOption('[name=status]', 'pending');
		await page.fill('[name=due_date]', '2026-01-20');

		// Submit form
		await page.click('[data-testid=save-todo]');

		// Wait for modal to close
		await expect(page.locator('.modal')).not.toBeVisible();

		// Verify todo appears in list
		await expect(page.locator('.task-title')).toContainText('Test Task');
	});

	test('should edit an existing todo', async ({ page }) => {
		// Click on a todo to edit
		const todoItem = page.locator('.task-item').first();
		await todoItem.click();

		// Wait for modal
		await expect(page.locator('.modal')).toBeVisible();

		// Update title
		await page.fill('[name=title]', 'Updated Task Title');

		// Save changes
		await page.click('[data-testid=save-todo]');

		// Verify updated title appears
		await expect(page.locator('.task-title')).toContainText('Updated Task Title');
	});

	test('should complete a todo', async ({ page }) => {
		// Find the complete button for a todo
		const completeButton = page.locator('[data-testid=complete-todo]').first();
		await completeButton.click();

		// Verify todo is marked as completed
		await expect(page.locator('.task-item.completed').first()).toBeVisible();

		// Verify status badge shows completed
		await expect(page.locator('.badge-completed').first()).toBeVisible();
	});

	test('should delete a todo', async ({ page }) => {
		// Get initial count of todos
		const initialCount = await page.locator('.task-item').count();

		// Click delete button
		const deleteButton = page.locator('[data-testid=delete-todo]').first();
		await deleteButton.click();

		// Confirm deletion in confirmation dialog
		await page.locator('[data-testid=confirm-delete]').click();

		// Verify todo count decreased
		await expect(page.locator('.task-item')).toHaveCount(initialCount - 1);
	});

	test('should filter todos by status', async ({ page }) => {
		// Select status filter
		await page.selectOption('[name=status-filter]', 'pending');

		// Verify only pending todos are shown
		const statusBadges = page.locator('.badge-pending');
		await expect(statusBadges).toHaveCount(await page.locator('.task-item').count());

		// Change to completed
		await page.selectOption('[name=status-filter]', 'completed');

		// Verify only completed todos are shown
		const completedBadges = page.locator('.badge-completed');
		await expect(completedBadges).toHaveCount(await page.locator('.task-item').count());
	});

	test('should filter todos by project', async ({ page }) => {
		// Assume a project exists
		await page.selectOption('[name=project-filter]', '1'); // Project ID 1

		// Verify todos are filtered
		const todos = page.locator('.task-item');
		await expect(todos.first().locator('.project-badge')).toBeVisible();
	});

	test('should search todos', async ({ page }) => {
		// Enter search query
		await page.fill('[name=search]', 'important');

		// Submit search
		await page.press('[name=search]', 'Enter');

		// Verify search results contain query
		const results = page.locator('.task-item');
		const count = await results.count();

		for (let i = 0; i < count; i++) {
			const text = await results.nth(i).textContent();
			expect(text?.toLowerCase()).toContain('important');
		}
	});

	test('should validate required fields when creating todo', async ({ page }) => {
		// Click add todo button
		await page.click('[data-testid=add-todo-button]');

		// Try to submit empty form
		await page.click('[data-testid=save-todo]');

		// Should show validation error
		await expect(page.locator('[data-error=title]')).toContainText('Title is required');
	});

	test('should show todo details with all fields', async ({ page }) => {
		// Create a todo with all fields
		await page.click('[data-testid=add-todo-button]');
		await page.fill('[name=title]', 'Detailed Task');
		await page.fill('[name=description]', 'Detailed description');
		await page.selectOption('[name=priority]', 'urgent');
		await page.fill('[name=due_date]', '2026-01-25');
		await page.fill('[name=estimated_hours]', '5');
		await page.fill('[name=tags]', 'tag1,tag2,tag3');
		await page.fill('[name=context]', '@work');
		await page.click('[data-testid=save-todo]');

		// Click to view details
		const todo = page.locator('.task-title').filter({ hasText: 'Detailed Task' });
		await todo.click();

		// Verify all fields are displayed
		await expect(page.locator('[data-field=description]')).toContainText('Detailed description');
		await expect(page.locator('[data-field=priority]')).toContainText('urgent');
		await expect(page.locator('[data-field=estimated_hours]')).toContainText('5');
		await expect(page.locator('[data-field=tags]')).toContainText('tag1');
		await expect(page.locator('[data-field=context]')).toContainText('@work');
	});
});
