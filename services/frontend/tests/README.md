# Frontend E2E Tests

This directory contains end-to-end tests for the TaskManager SvelteKit frontend using Playwright. Tests are executable and run against a live backend with a dedicated test database.

## Current State

- 13 test files in `tests/e2e/`
- 139 total test cases (134 run in CI; 5 screenshot tests are CI-excluded)
- Test infrastructure configured (Playwright, cross-browser testing)
- Isolated test database setup (automatic reset before tests)
- Backend API integration via test environment

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

## Test Files

### `auth-flow.spec.ts` (6 tests)

Tests user authentication flows:

- User registration with validation
- Login with valid/invalid credentials
- Logout and session cleanup
- Protected route redirection

### `calendar-drag-drop.spec.ts` (13 tests)

Tests drag-and-drop calendar (2 active, 11 skipped pending UI updates):

- 3-week calendar view rendering
- Week navigation (previous/next)
- Today highlighting
- Display todos on calendar
- Drag-and-drop todos between dates
- Project color integration
- Priority styling
- Double-click and keyboard interaction
- Mobile tap behavior
- Pending-only filtering

### `calendar-expand-collapse.spec.ts` (6 tests)

Tests the expand/collapse all button for overflowed tasks:

- Expand all / collapse all button visibility and toggling
- Manual per-day expand syncs global button state
- Week navigation resets expanded state

### `calendar-subtask-drag.spec.ts` (9 tests)

Tests subtask rendering and drag behavior in the calendar:

- Subtasks render inside the dndzone and are draggable
- Subtask parent info badge display
- Subtasks count toward overflow limit
- Drop target coverage (empty cells, filled cells)
- Dragging parent tasks and subtasks between days
- Parent task stays after subtask date change

### `deadline-type.spec.ts` (18 tests)

Tests the deadline_type field across form UI, create, edit, and display:

- Form UI: select options, default value, all values selectable
- Create with each deadline type (flexible, preferred, firm, hard)
- Edit: pre-population and update of deadline type
- Display: badges/pills in detail, list, calendar, and home views
- API: create, default, and update persistence

### `home-page.spec.ts` (8 tests)

Tests the home dashboard page:

- Greeting and date display
- Due today and feed panels
- Empty state, overdue section, task links
- Authentication redirect

### `list-view-ux.spec.ts` (9 tests)

Tests list view UX improvements:

- Priority color legend visibility
- CSS tooltips on action buttons
- Task card info density (date, priority labels)
- Masonry layout for project cards
- Inbox label for unassigned tasks, sort order

### `project-filter.spec.ts` (6 tests)

Tests project filter persistence and auto-set behavior:

- Auto-fill project when filter is active on new task creation
- No pre-fill when no filter is active
- Persist filter across navigation and page refresh
- Clear stale filter when project is deleted
- Clear persisted filter when "All Projects" is selected

### `readme-screenshots.spec.ts` (5 tests, CI-excluded)

Screenshot generation for README documentation (manual use only):

- Login, registration, dashboard, settings, and full-page screenshots

### `snippets.spec.ts` (11 tests)

Tests snippet CRUD and browsing:

- List page: empty state, populated list, search filtering
- Create, view, edit, and delete snippets
- Category filter chips and tag display
- Create page with category query param

### `todo-flow.spec.ts` (9 tests)

Tests todo management (all 9 tests currently skipped pending UI updates):

- Create, edit, complete, delete todos
- Filter by status and project
- Search
- Form validation (required fields)
- Todo detail view with all fields

### `ux-improvements.spec.ts` (22 tests)

Tests UX improvements across multiple features:

- Search modal (Ctrl+K, toolbar button, results, navigation, backdrop close)
- Toast notifications with undo on task completion
- Task summary stats bar (total, overdue, due today)
- Calendar improvements (Today button, single-click detail, overflow)
- User dropdown menu (open, close, toggle, settings link)

### `wiki.spec.ts` (17 tests)

Tests wiki page CRUD and navigation:

- List page: search, empty state, populated list
- Create, view, edit, and delete pages
- Wiki link rendering, parent/child relationships
- Breadcrumb navigation, move page via modal
- Tag display and tag filter chips

## Test Helpers

### `helpers/test-utils.ts`

Shared utilities used across test files:

- `registerAndLogin()` - Register a new user and log in
- `login()` - Log in with existing test credentials
- `createTodoViaAPI()` - Create a todo via the backend API
- `createSnippetViaAPI()` - Create a snippet via the backend API
- `createWikiPageViaAPI()` - Create a wiki page via the backend API
- `getFutureDate()` / `getPastDate()` / `getTodayDate()` - Date helpers
- `waitForNetworkIdle()` / `waitForApiResponse()` - Network wait helpers
- `takeScreenshot()` - Screenshot capture helper

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

## Related Documentation

- [Playwright Documentation](https://playwright.dev/)
- [SvelteKit Testing](https://kit.svelte.dev/docs/testing)
