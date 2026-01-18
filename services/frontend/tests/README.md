# Frontend E2E Tests

⚠️ **Status: Test Specifications - Not Yet Executable**

This directory contains end-to-end test specifications for the TaskManager SvelteKit frontend using Playwright. These tests serve as detailed specifications for the intended functionality and will become executable once the corresponding pages and features are implemented.

## Current State

- ✅ Test infrastructure configured (Playwright, cross-browser testing)
- ✅ 27 test specifications written covering all user flows
- ✅ Isolated test database setup (automatic reset before tests)
- ✅ Backend API integration via test environment
- ⏳ **Pending**: Complete page implementations

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

## Test Database Setup

### Automatic Isolated Environment

Tests run in a completely isolated environment:

- **Test Backend**: Port 8010 (separate from dev backend on 8000)
- **Test Database**: `taskmanager_test` (separate from dev database)
- **Frontend Preview**: Port 4173

### How It Works

1. **Database Reset**: Before tests start, the test database is automatically dropped and recreated
2. **Migrations**: Fresh migrations are applied to the test database
3. **Backend Start**: Test backend starts on port 8010 with `.env.test` config
4. **Frontend Build**: Frontend is built and previewed with proxy to test backend
5. **Test Execution**: Tests run against the isolated environment

This all happens automatically when you run `npm test` - no manual setup required!

### Test Database Configuration

Located in `/services/backend/.env.test`:

- Database name: `taskmanager_test`
- Backend port: 8010
- Faster bcrypt rounds for speed (4 vs 12 in development)

### Manual Database Reset

If you need to manually reset the test database:

```bash
cd ../backend
PYDANTIC_ENV_FILE=.env.test uv run python scripts/reset_test_db.py
```

### Test Credentials

Tests create users dynamically during registration tests:

- Username: `testuser`
- Email: `test@example.com`
- Password: `TestPass123!` # pragma: allowlist secret

**Security Note**: These credentials are for local testing only. Never use in production.

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
- Check if backend server started (port 8010)
- Check if PostgreSQL is running: `pg_isready`
- Verify network connectivity

**Database errors**

- **Error: Database already exists**: The reset script should handle this automatically
- **Error: Permission denied**: Ensure PostgreSQL user has CREATE DATABASE permission
- **Manual cleanup**: `dropdb taskmanager_test`

**Port conflicts**

- **Error: Port 8010 already in use**: A previous test backend may still be running
- **Fix**: `lsof -ti:8010 | xargs kill -9`
- **Error: Port 4173 already in use**: Kill existing preview server

**Backend connection failed**

- Ensure PostgreSQL is running: `pg_isready`
- Check backend logs in test output
- Verify `.env.test` configuration in backend directory

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
