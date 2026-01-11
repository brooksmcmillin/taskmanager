# Technical Debt & Future Improvements

## API Response Format Standardization

We implemented a standardized API response envelope format but had to partially revert it for frontend compatibility. The goal is to have consistent responses across all endpoints:

### Target Format
```json
// Success (list)
{ "data": [...], "meta": { "count": 10 } }

// Success (single item)
{ "data": { ... } }

// Error
{ "error": { "code": "AUTH_001", "message": "Invalid credentials" } }
```

### Current State (Legacy)
- `GET /api/todos` returns `{ tasks: [...] }` - should be `{ data: [...] }`
- `GET /api/projects` returns raw array `[...]` - should be `{ data: [...] }`
- `GET /api/todos/:id` returns item directly - should be `{ data: {...} }`
- `GET /api/projects/:id` returns item directly - should be `{ data: {...} }`
- `GET /api/oauth/clients` returns raw array - should be `{ data: [...] }`

### Migration Steps
1. Update all frontend fetch calls to extract `.data` from responses
2. Update frontend to handle `{ tasks }` → `{ data }` for todos
3. Switch API endpoints to use `apiResponse()` instead of `successResponse()`
4. Update OpenAPI spec to reflect new response format

### Files to Update
- `src/pages/index.astro` - todo loading
- `src/pages/projects.astro` - project loading  
- `src/components/DragDropCalendar.astro` - todo loading
- `src/components/TodoForm.astro` - project dropdown
- `src/pages/oauth-clients.astro` - client loading

---

## Frontend Error Handling Consistency

The new error format `{ error: { code, message } }` is only partially supported in the frontend.

### Fixed
- `src/pages/login.astro`
- `src/pages/register.astro`

### Needs Update
- `src/components/TodoForm.astro` - expects `error.message` at top level
- `src/components/ProjectForm.astro` - expects `error.message` at top level
- `src/pages/oauth-clients.astro` - mixed formats (some inline, some from API)

### Suggested Helper
Create a shared error extraction utility:
```javascript
function getErrorMessage(data) {
  if (typeof data.error === 'object') return data.error.message;
  if (typeof data.error === 'string') return data.error;
  return data.message || 'Unknown error';
}
```

---

## OAuth Clients Endpoint Modernization

The `/api/oauth/clients.js` endpoint uses inline Response objects instead of the shared utilities. Should be migrated to use:
- `errors.*` for error responses
- `successResponse()` / `apiResponse()` for success responses
- `validateRequired()` for input validation

---

## Pagination Support

The `paginatedResponse()` helper exists in `apiResponse.js` but isn't used anywhere. Consider adding pagination to:
- `GET /api/todos` (for large task lists)
- `GET /api/projects` (less critical)
- `GET /api/oauth/clients` (less critical)

---

## Remove Redundant dotenv Calls

The `dotenv` package is called in `src/lib/db.js` but environment variables are already set by docker-compose's `env_file` directive. The dotenv call is redundant in production but useful for local development without docker.

Consider:
- Making dotenv conditional: `if (process.env.NODE_ENV !== 'production') config()`
- Or removing dotenv entirely and requiring docker-compose or manual env setup

---

## Test Coverage

After stabilization, add tests for:
- [ ] New error code responses
- [ ] Validator functions in `validators.js`
- [ ] API response format consistency
- [ ] OAuth public client flow
- [ ] Recurring tasks CRUD operations
- [ ] Recurring task generation logic
- [ ] `calculateNextDueDate` edge cases (month boundaries, leap years)

---

## Recurring Tasks Enhancements

The initial recurring tasks implementation (v1) supports basic patterns. Future enhancements to consider:

### Complex Recurrence Patterns
- [ ] Biweekly recurrence (every 2 weeks on specific days)
- [ ] "Nth weekday of month" patterns (e.g., "3rd Tuesday of every month")
- [ ] "Last day of month" pattern
- [ ] Custom RRULE-style patterns for full iCalendar compatibility

### Fixed Schedule Mode (`skip_missed: false`)
- [ ] Generate backlog of missed tasks when user returns after absence
- [ ] Option to bulk-complete or bulk-skip missed instances
- [ ] Dashboard widget showing overdue recurring task instances

### User Interface
- [ ] Frontend UI for creating/editing recurring tasks
- [ ] Visual indicator on task cards showing recurrence pattern
- [ ] "Edit series" vs "Edit this instance" option when modifying recurring tasks
- [ ] Recurrence summary text (e.g., "Every Friday" or "Monthly on the 15th")

### Background Processing
- [ ] Optional scheduled job runner for large-scale deployments
- [ ] Batch generation of recurring tasks for performance
- [ ] Configurable look-ahead period (generate tasks N days in advance)

### Additional Features
- [ ] Pause/resume recurring tasks without deleting
- [ ] Recurring task statistics (completion rate, average delay)
- [ ] Snooze a recurring task instance to next occurrence
- [ ] Integration with calendar export (iCal format)
