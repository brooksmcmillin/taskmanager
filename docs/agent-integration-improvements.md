# Agent Integration Improvements

This document tracks implemented features and planned improvements for the task manager agent integration.

## Implemented Features

### Database Schema
- Added `agent_actionable` (boolean) - Whether agent can complete task autonomously
- Added `action_type` (enum) - Type of action: research, code, email, document, purchase, schedule, call, errand, manual, review, data_entry, other
- Added `agent_status` (enum) - Agent processing status: pending_review, in_progress, completed, blocked, needs_human
- Added `agent_notes` (text) - Agent-generated context and research notes
- Added `blocking_reason` (string) - Why agent cannot proceed

### Rule-Based Inference
- Automatic classification at task creation based on title/description keywords
- Keyword patterns for each action type with actionability defaults
- Returns (None, None) for unrecognized patterns, allowing agent LLM classification

### MCP Tools
- `get_agent_tasks` - Filter tasks for agent work queue (due_today, agent_actionable_only, unclassified_only)
- `classify_task` - Classify unclassified tasks with action_type and agent_actionable
- `add_agent_note` - Append research notes to a task
- `set_agent_status` - Update agent processing status

---

## Future Improvements

### Backend (services/backend/)

1. **Agent Activity Log Table**
   - Create `agent_activities` table to track all agent actions
   - Fields: task_id, agent_id, action (researched, attempted, completed), notes, success, created_at
   - Helps with debugging and understanding agent behavior patterns

2. **Project-Level Defaults**
   - Add `default_agent_actionable` and `default_action_type` to Project model
   - Inherit defaults when creating tasks in a project
   - Example: All tasks in "Research" project default to agent_actionable=True

3. **Steps/Checklist Field**
   - Add `steps` JSONB field for lightweight task breakdown
   - Structure: `[{step, status, agent_can_do}]`
   - Alternative to subtasks for simpler decomposition

4. **Action Requirements Field**
   - Add `action_requirements` JSONB field
   - Structure: `{tools: [], context_needed: [], external_apis: [], human_approval_required}`
   - Helps agent determine capability before attempting

5. **Enhanced Filtering API**
   - Add `/api/todos/agent` endpoint with agent-optimized defaults
   - Support filtering by agent_status, action_type, agent_actionable
   - Include time-to-deadline sorting for priority

6. **Webhook on Agent Status Change**
   - Emit webhooks when agent_status changes
   - Enable external systems to react to agent progress

### MCP Resource Server (services/mcp-resource/)

1. **Batch Classification Tool**
   - `classify_tasks_batch` - Classify multiple tasks in one call
   - More efficient for initial classification sweep

2. **Task Context Summarization**
   - `get_task_context` - Return task with related tasks, project info, recent agent activity
   - Helps agent understand full context before acting

3. **Agent Capability Declaration**
   - Tool to register what capabilities the connected agent has
   - Filter tasks based on agent capabilities

4. **Progress Reporting Tool**
   - `report_progress` - Update task with incremental progress
   - Better than just notes for long-running tasks

5. **Dependency Detection**
   - `check_dependencies` - Identify if task depends on other incomplete tasks
   - Prevent agent from working on blocked tasks

### Python SDK (packages/taskmanager-sdk/)

1. **Agent Helper Methods**
   - `get_actionable_tasks()` - Pre-filtered for agent
   - `classify_and_update(task_id, action_type, actionable)` - Combined operation
   - `append_note(task_id, note)` - Convenience wrapper

2. **Classification Helper**
   - `infer_classification(title, description)` - Client-side rule matching
   - Useful when agent wants to preview before setting

3. **Task Queue Iterator**
   - Generator that yields agent-actionable tasks in priority order
   - Handles pagination automatically

### Frontend (services/frontend/)

1. **Agent Status Display**
   - Show agent_status badge on tasks
   - Filter views by agent status
   - Display agent_notes in expandable section

2. **Manual Override UI**
   - Allow user to manually set agent_actionable and action_type
   - Override agent classification when needed

3. **Agent Activity Timeline**
   - Show what agent has done on each task
   - Display agent notes with timestamps

4. **Agent Preferences Settings**
   - Let users configure which action types agent can work on
   - Set default behaviors per project

### Agent Workflow Patterns

1. **Daily Review Pattern**
   ```
   1. get_agent_tasks(due_today=True, unclassified_only=True)
   2. For each: classify_task() based on LLM analysis
   3. get_agent_tasks(due_today=True, agent_actionable_only=True)
   4. For each actionable task:
      - set_agent_status(task_id, "in_progress")
      - Do the work
      - add_agent_note(task_id, findings)
      - complete_task() or set_agent_status(task_id, "needs_human", reason)
   ```

2. **Research Enhancement Pattern**
   ```
   1. get_agent_tasks(action_type="research")
   2. For each:
      - Gather information
      - add_agent_note(task_id, research_findings)
      - set_agent_status(task_id, "completed")
      (Don't complete the task itself - just the research portion)
   ```

3. **Triage Pattern**
   ```
   1. get_agent_tasks(unclassified_only=True)
   2. For each:
      - Analyze with LLM
      - classify_task(task_id, type, actionable, blocking_reason)
   3. Report summary to user
   ```

---

## Migration Notes

After pulling these changes, run:
```bash
cd services/backend
uv run alembic upgrade head
```

This will add the new agent fields to the todos table.
