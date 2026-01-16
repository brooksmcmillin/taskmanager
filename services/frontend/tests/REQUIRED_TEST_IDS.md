# Required data-testid Attributes

This document lists all `data-testid` attributes that must be added to components for E2E tests to run successfully.

## Priority: Critical (Blockers)

These test IDs are required for tests to run at all:

### Authentication Pages

**Login Page (`/login`)**

- None required (uses name attributes on form fields)

**Register Page (`/register`)**

- None required (uses name attributes on form fields)

### Navigation Component

```svelte
<!-- Navigation.svelte -->
<button data-testid="logout-button" on:click={handleLogout}>Logout</button>
```

### Todo Management

**Dashboard / Todo List**

```svelte
<!-- Dashboard page or TodoList component -->
<button data-testid="add-todo-button" on:click={openAddModal}>Add Todo</button>

<!-- For each todo item -->
<div class="task-item" data-testid="todo-item-{todo.id}">
	<button data-testid="complete-todo" on:click={() => completeTodo(todo.id)}>Complete</button>
	<button data-testid="delete-todo" on:click={() => deleteTodo(todo.id)}>Delete</button>
</div>

<!-- Confirmation dialog -->
<button data-testid="confirm-delete" on:click={confirmDelete}>Confirm</button>
```

**TodoModal Component**

```svelte
<!-- TodoModal.svelte -->
<Modal>
	<TodoForm>
		<button type="submit" data-testid="save-todo">Save</button>
	</TodoForm>
</Modal>
```

### Calendar Component

**DragDropCalendar.svelte**

```svelte
<div class="flex gap-4">
	<button class="btn btn-secondary btn-sm" data-testid="prev-week" on:click={prevWeek}>
		← Previous
	</button>
	<button class="btn btn-secondary btn-sm" data-testid="next-week" on:click={nextWeek}>
		Next →
	</button>
</div>
```

### Project Management

**Projects Page**

```svelte
<button data-testid="add-project-button" on:click={openAddModal}>Add Project</button>
```

## Priority: High (Improves Test Reliability)

These test IDs would improve test stability but tests could work without them:

### Form Fields

While tests currently use `[name=fieldname]` selectors, adding test IDs would be more stable:

```svelte
<input
  type="text"
  name="title"
  data-testid="todo-title-input"
  bind:value={todo.title}
/>

<input
  type="date"
  name="due_date"
  data-testid="todo-due-date-input"
  bind:value={todo.due_date}
/>

<select
  name="priority"
  data-testid="todo-priority-select"
  bind:value={todo.priority}
>
```

### Filter Controls

```svelte
<select name="status-filter" data-testid="status-filter">
	<option value="all">All</option>
	<option value="pending">Pending</option>
	<option value="completed">Completed</option>
</select>

<select name="project-filter" data-testid="project-filter">
	<!-- project options -->
</select>

<input type="search" name="search" data-testid="todo-search-input" placeholder="Search todos..." />
```

## Priority: Medium (Better Test Semantics)

These would make tests more semantic but aren't strictly required:

### Error Messages

```svelte
<p class="error-message" data-testid="error-{fieldName}">
	{errorMessage}
</p>

<!-- Specific examples -->
<p data-testid="error-username">Username is required</p>
<p data-testid="error-email">Invalid email format</p>
<p data-testid="error-password">Password too weak</p>
```

### Data Display Fields

```svelte
<!-- Todo detail view -->
<div data-testid="field-description">{todo.description}</div>
<div data-testid="field-priority">{todo.priority}</div>
<div data-testid="field-estimated-hours">{todo.estimated_hours}</div>
<div data-testid="field-tags">{todo.tags.join(', ')}</div>
<div data-testid="field-context">{todo.context}</div>
```

## Implementation Checklist

When implementing pages, ensure these attributes are added:

### Phase 1: Critical Path (Authentication & Basic CRUD)

- [ ] Navigation logout button
- [ ] Add todo button
- [ ] Save todo button (in modal)
- [ ] Complete todo button
- [ ] Delete todo button
- [ ] Delete confirmation button

### Phase 2: Calendar & Navigation

- [ ] Calendar previous week button
- [ ] Calendar next week button

### Phase 3: Enhanced Reliability

- [ ] Form field test IDs
- [ ] Filter control test IDs
- [ ] Error message test IDs
- [ ] Data display field test IDs

## Usage in Tests

```typescript
// Recommended pattern
await page.click('[data-testid=add-todo-button]');

// Current fallback (less stable)
await page.click('button:has-text("Add Todo")');

// Avoid (most fragile)
await page.click('.btn.btn-primary.add-todo');
```

## Testing the Implementation

To verify all required test IDs are present:

```bash
# Run a single test to check for missing test IDs
npx playwright test tests/e2e/todo-flow.spec.ts:21 --debug

# Look for errors like:
# "Timeout waiting for selector [data-testid=add-todo-button]"
```

## Auto-generation Script (Future Enhancement)

Consider creating a script to validate all required test IDs exist:

```typescript
// validate-test-ids.ts
const requiredTestIds = [
	'logout-button',
	'add-todo-button',
	'save-todo',
	'complete-todo',
	'delete-todo'
	// ... etc
];

// Scan components and verify each ID exists
```

---

**Last Updated**: 2026-01-15
**Status**: Specification - Awaiting Implementation
