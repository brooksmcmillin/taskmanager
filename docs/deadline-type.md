# Deadline Type

The `deadline_type` field indicates how strictly a task's due date should be respected. This is orthogonal to priority — a task can be high-priority with a flexible deadline, or low-priority with a hard deadline.

## Values

| Value | Description | When to Use |
|-------|-------------|-------------|
| `flexible` | Due date is a loose suggestion; reschedule freely | Internal goals, nice-to-haves, aspirational targets |
| `preferred` | Soft target date; try to hit it but okay to slip | Most tasks (this is the default) |
| `firm` | Avoid moving unless necessary | External dependencies, team commitments, planned releases |
| `hard` | Immovable deadline; never reschedule | Legal deadlines, contractual obligations, regulatory filings, bill payments |

## Default Behavior

When no `deadline_type` is specified, tasks default to `preferred`.

## API Usage

### Creating a task with deadline_type

```bash
POST /api/todos
{
    "title": "File quarterly taxes",
    "due_date": "2026-04-15",
    "deadline_type": "hard",
    "priority": "high"
}
```

### Filtering tasks by deadline_type

```bash
GET /api/todos?deadline_type=hard
GET /api/todos?deadline_type=firm&start_date=2026-03-01&end_date=2026-03-31
```

### Sorting by deadline_type

Sort tasks by deadline strictness (hard first, then firm, preferred, flexible):

```bash
GET /api/todos?order_by=deadline_type
```

### Updating deadline_type

```bash
PUT /api/todos/{id}
{
    "deadline_type": "firm"
}
```

## MCP Tool Usage

The `get_tasks` MCP tool supports filtering and sorting by deadline_type:

```json
{
    "tool": "get_tasks",
    "arguments": {
        "deadline_type": "hard",
        "order_by": "deadline_type"
    }
}
```

Task responses from MCP tools include `deadline_type` in the output:

```json
{
    "id": "task_123",
    "title": "File quarterly taxes",
    "deadline_type": "hard",
    "due_date": "2026-04-15",
    "priority": "high"
}
```

## For Automated Rescheduling Agents

When building agents that reschedule tasks, use `deadline_type` to make smart decisions:

- **flexible**: Reschedule freely to balance workload
- **preferred**: Try to keep the date, but slip if needed to accommodate firm/hard deadlines
- **firm**: Only move if absolutely necessary (e.g., blocking dependency isn't met)
- **hard**: Never reschedule — flag conflicts to the user instead

### Example: Priority vs Deadline Type

| Task | Priority | Deadline Type | Agent Behavior |
|------|----------|---------------|----------------|
| "Review blog post" | high | flexible | Reschedule if day is overloaded |
| "Pay electric bill" | low | hard | Never move — external deadline |
| "Sprint demo prep" | high | firm | Avoid moving; warn user if at risk |
| "Read industry report" | low | flexible | First to reschedule when needed |

## Frontend Display

In the UI, deadline types are displayed as color-coded badges:

- **Flexible**: Gray
- **Preferred**: Blue (default, often hidden to reduce noise)
- **Firm**: Orange
- **Hard**: Red

The task list can be filtered by deadline type using the filter dropdown in the toolbar.
