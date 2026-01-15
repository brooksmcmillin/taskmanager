# Frontend E2E Tests

This directory contains end-to-end tests for the TaskManager SvelteKit frontend using Playwright.

## Setup

Install dependencies (including Playwright browsers):

```bash
npm install
npx playwright install
```

## Running Tests

```bash
# Run all tests
npm test

# Run tests in UI mode (interactive)
npm run test:ui

# Run tests in debug mode
npm run test:debug

# Run specific test file
npx playwright test tests/e2e/auth-flow.spec.ts

# Run tests in specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit

# Show test report
npx playwright show-report playwright-report
```

## Test Structure

### `auth-flow.spec.ts`
Tests user authentication flows:
- User registration with validation
- Login with valid/invalid credentials
- Logout and session cleanup
- Protected route redirection

### `todo-flow.spec.ts`
Tests todo management:
- Create new todos with all fields
- Edit existing todos
- Complete and delete todos
- Filter by status and project
- Search functionality
- Form validation

### `calendar-drag-drop.spec.ts`
Tests drag-and-drop calendar:
- 3-week calendar view rendering
- Week navigation (previous/next)
- Display todos on calendar
- Drag-and-drop todos between dates
- Project color integration
- Priority styling
- Double-click to edit
- Keyboard accessibility
- Pending-only filtering

## Test Configuration

Configuration is in `playwright.config.ts`:
- Tests run against `http://localhost:4173` (preview server)
- Automatic server startup before tests
- Screenshots and videos on failure
- HTML report generation
- Cross-browser testing (Chromium, Firefox, WebKit)

## Test Data

Tests assume:
- A test user exists with credentials:
  - Username: `testuser`
  - Password: `TestPass123!` # pragma: allowlist secret
- Backend API is running and accessible
- Database is in a clean state

## CI/CD Integration

Tests are designed to run in CI environments:
- Set `CI=true` environment variable
- Tests run sequentially in CI (1 worker)
- 2 retries on failure
- No interactive prompts

## Writing New Tests

Follow these patterns:

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
    test.beforeEach(async ({ page }) => {
        // Login or setup common state
    });

    test('should do something', async ({ page }) => {
        // 1. Navigate
        await page.goto('/path');

        // 2. Interact
        await page.click('[data-testid=button]');

        // 3. Assert
        await expect(page.locator('.result')).toBeVisible();
    });
});
```

### Best Practices

1. **Use `data-testid` attributes** for reliable selectors
2. **Wait for elements** with `waitForSelector()` when needed
3. **Use page object models** for complex pages
4. **Clean up state** in `beforeEach` or `afterEach`
5. **Test user flows**, not implementation details
6. **Make tests independent** - each test should work standalone

## Debugging

### Debug Mode
```bash
npm run test:debug
```

Opens Playwright Inspector for step-by-step debugging.

### Trace Viewer
```bash
npx playwright show-trace trace.zip
```

View traces from failed tests.

### Console Logs
Add `console.log()` in tests or use:
```typescript
await page.evaluate(() => console.log('Browser console'));
```

## Troubleshooting

**Tests fail with "Timeout"**
- Increase timeout in config
- Check if server is running
- Verify network connectivity

**Elements not found**
- Check selectors match actual HTML
- Use `page.locator().all()` to debug
- Wait for dynamic content with `waitForSelector()`

**Drag-and-drop not working**
- Verify `svelte-dnd-action` is installed
- Check that elements have proper drag handlers
- Use Playwright's `dragTo()` method

## Coverage

Target coverage goals:
- User flows: 100%
- Component interactions: 90%+
- Error handling: 80%+

## Related Documentation

- [Playwright Documentation](https://playwright.dev/)
- [SvelteKit Testing](https://kit.svelte.dev/docs/testing)
- Migration Plan: `docs/MIGRATION_PLAN.md` (Section 3.3)
