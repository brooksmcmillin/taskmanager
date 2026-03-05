# Test Coverage Summary

This document provides an overview of the E2E test suite for the TaskManager SvelteKit frontend.

## Test Files Overview

| Test File                        | Test Count | Coverage Area                  |
| -------------------------------- | ---------- | ------------------------------ |
| `auth-flow.spec.ts`              | 6          | Authentication                 |
| `calendar-drag-drop.spec.ts`     | 13         | Calendar & drag-and-drop       |
| `calendar-expand-collapse.spec.ts` | 6        | Calendar overflow expand/collapse |
| `calendar-subtask-drag.spec.ts`  | 9          | Subtask dragging & drop targets |
| `deadline-type.spec.ts`          | 16         | Deadline type feature           |
| `home-page.spec.ts`              | 8          | Home dashboard                 |
| `list-view-ux.spec.ts`           | 9          | List view UX                   |
| `project-filter.spec.ts`         | 6          | Project filter persistence     |
| `readme-screenshots.spec.ts`     | 5          | Screenshot generation (CI-excluded) |
| `snippets.spec.ts`               | 11         | Snippets CRUD                  |
| `todo-flow.spec.ts`              | 10         | Todo management                |
| `ux-improvements.spec.ts`        | 19         | Search, toast, stats, calendar UX |
| `wiki.spec.ts`                   | 18         | Wiki pages CRUD & navigation   |
| **Total**                        | **136**    | **13 files, all core flows**   |

**Note**: `readme-screenshots.spec.ts` (5 tests) is excluded from CI runs. 131 tests execute in CI.

## User Flow Coverage

### 1. Authentication Flow (6 tests)

**Covered Scenarios:**

- New user registration with field validation
- Successful login with valid credentials
- Failed login with invalid credentials and error display
- Logout with session cleanup
- Form validation (email, password strength)
- Protected route redirection to login

### 2. Todo Management Flow (10 tests)

**Covered Scenarios:**

- Create new todo with modal form
- Edit existing todo
- Complete todo (status change)
- Delete todo with confirmation
- Filter todos by status (pending, completed)
- Filter todos by project
- Full-text search
- Form validation (required fields)
- Display all todo fields (description, priority, tags, context, etc.)
- Todo detail view

**Note:** Most tests in this file are currently marked with `test.skip` pending UI updates.

### 3. Calendar Drag-Drop Flow (13 tests)

**Covered Scenarios:**

- Display 3-week calendar (21 days) with day headers
- Highlight current day
- Navigate between weeks (previous/next)
- Display todos on calendar by due date
- Drag todo from one date to another
- Show drop target indicator during drag
- Display project colors on calendar tasks
- Show priority styling on tasks
- Open edit modal on double-click
- Keyboard navigation (Enter/Space to edit)
- Single tap on mobile
- Show only pending todos (filter out completed)

### 4. Calendar Expand/Collapse (6 tests)

**Covered Scenarios:**

- Expand all button hidden when no overflow
- Expand all button appears on overflow (>3 tasks)
- Toggling expand/collapse all
- Manual per-day expand syncs global button
- Week navigation resets expanded state

### 5. Calendar Subtask Dragging (9 tests)

**Covered Scenarios:**

- Subtasks render inside dndzone
- Subtasks have grab cursor
- Parent info badge on subtasks
- Subtasks count toward overflow limit
- Tasks-container fills day cell vertically
- Empty day cells have tall drop targets
- Drag parent task via empty area
- Move subtask due date updates calendar position
- Parent task remains after subtask date change

### 6. Deadline Type Feature (16 tests)

**Covered Scenarios:**

- Form UI: deadline_type select with 4 options, default value
- Create with each deadline type (flexible, preferred, firm, hard)
- Edit: pre-populate and update deadline type
- Display: badge in detail page, pill in list view, label on calendar, pill on home
- Preferred type hides pill/label (default, no visual indicator)
- API: create, default, update and persist

### 7. Home Page (8 tests)

**Covered Scenarios:**

- Greeting and date display
- Both panels visible (Due Today, Feed)
- Empty state when no tasks due today
- Task due today display with badge count
- Overdue tasks in separate section
- Task links to detail page
- Feed panel with empty or populated state
- Authentication redirect

### 8. List View UX (9 tests)

**Covered Scenarios:**

- Priority color legend in list view (hidden in calendar view)
- CSS tooltips (data-tooltip, aria-label) on action buttons
- "No date" vs formatted due date display
- Priority label always shown
- CSS columns masonry layout
- "Inbox" label for unassigned tasks, sorted last

### 9. Project Filter (6 tests)

**Covered Scenarios:**

- Auto-fill project on new task when filter is active
- No pre-fill when no filter active
- Persist filter across navigation and page refresh
- Clear stale filter when project is deleted
- Clear persisted filter on "All Projects" selection

### 10. Screenshots (5 tests, CI-excluded)

Manual-only screenshot generation for README documentation.

### 11. Snippets (11 tests)

**Covered Scenarios:**

- List page: empty state, populated list, search filtering
- Create, view, edit, delete snippets
- Category filter chips
- Tags displayed on view page
- Create page with category query param

### 12. UX Improvements (19 tests)

**Covered Scenarios:**

- Search modal: Ctrl+K shortcut, toolbar button, results display, navigation, backdrop close, no results state
- Toast notifications: undo on completion (tasks page and home page), dismiss with close button
- Task summary stats bar: total count, overdue count, due today count
- Calendar: Today button, navigate to current week, single-click task detail, +N more overflow, expand/collapse overflow
- User dropdown: open on click, close on outside click, toggle on repeated clicks, settings link

### 13. Wiki Pages (18 tests)

**Covered Scenarios:**

- List page: populated list, search filtering, empty state
- Create, view, edit, delete pages
- Create page with title query param
- View page by slug, not-found state
- Wiki links render as clickable links
- Create page with parent, breadcrumb navigation
- Child pages section on view page
- Tags displayed on view page
- Move page to new parent or root via modal
- Tag filter chips on list page

## Test Quality

### Reliability

- **Independent tests**: Each test can run standalone
- **Clean state**: `beforeEach` hooks ensure consistent state with fresh user registration
- **Dynamic data**: Tests use unique timestamps to avoid conflicts
- **Cross-browser**: Tests run on Chromium, Firefox, WebKit

### Maintainability

- **Shared helpers**: `test-utils.ts` provides reusable functions for login, data creation, and waiting
- **API-based setup**: Tests create data via API calls rather than UI clicks for reliability
- **Clear naming**: Descriptive test names follow "should..." pattern

### Performance

- **Parallel execution**: Tests run in parallel (except CI)
- **Timeout handling**: Appropriate timeouts for async operations
- **Retry logic**: 2 retries in CI for flaky tests

## Running Tests

```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Run specific test
npx playwright test tests/e2e/calendar-drag-drop.spec.ts

# CI mode
CI=true npm test
```

## Related Documentation

- Test Setup: `tests/README.md`
- Playwright Config: `playwright.config.ts`

---

**Last Updated**: 2026-03-05
