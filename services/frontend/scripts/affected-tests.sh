#!/usr/bin/env bash
# Determine which E2E test specs are affected by changed files.
# Outputs a space-separated list of spec file paths (relative to tests/e2e/).
# Empty output means "run all tests".
#
# Usage:
#   BASE_REF=origin/main bash scripts/affected-tests.sh

set -euo pipefail

BASE_REF="${BASE_REF:-origin/main}"

# Get changed files relative to repo root
changed_files=$(git diff --name-only "$BASE_REF"...HEAD 2>/dev/null || git diff --name-only "$BASE_REF" HEAD)

# If no changed files, run all tests
if [ -z "$changed_files" ]; then
  exit 0
fi

# Filter to frontend and backend changes only
relevant_changes=$(echo "$changed_files" | grep -E '^services/(frontend|backend)/' || true)

# If no relevant changes, nothing to run (other services changed)
if [ -z "$relevant_changes" ]; then
  echo ""
  exit 0
fi

# Check for backend changes — any backend change triggers all tests
if echo "$relevant_changes" | grep -qE '^services/backend/'; then
  exit 0
fi

# From here on, only frontend changes exist
frontend_changes=$(echo "$relevant_changes" | sed 's|^services/frontend/||')

# Shared/core files that trigger ALL tests
run_all=false
while IFS= read -r file; do
  case "$file" in
    src/lib/api/*) run_all=true ;;
    src/lib/stores/todos.ts) run_all=true ;;
    src/lib/stores/createCrudStore.ts) run_all=true ;;
    src/lib/types.ts) run_all=true ;;
    src/routes/+layout*) run_all=true ;;
    src/lib/components/Navigation.svelte) run_all=true ;;
    src/lib/components/Modal.svelte) run_all=true ;;
    src/lib/components/TodoForm.svelte) run_all=true ;;
    src/app.*) run_all=true ;;
    playwright.config.*) run_all=true ;;
    tests/helpers/*) run_all=true ;;
    svelte.config.*) run_all=true ;;
    vite.config.*) run_all=true ;;
    tsconfig.*) run_all=true ;;
    package*.json) run_all=true ;;
  esac
done <<< "$frontend_changes"

if [ "$run_all" = true ]; then
  exit 0
fi

# Feature-specific mappings: collect affected specs
declare -A specs

while IFS= read -r file; do
  case "$file" in
    src/routes/login/* | src/routes/register/*)
      specs["tests/e2e/auth-flow.spec.ts"]=1
      ;;
    src/routes/tasks/* | src/lib/components/DragDropCalendar.svelte)
      specs["tests/e2e/calendar-drag-drop.spec.ts"]=1
      specs["tests/e2e/calendar-expand-collapse.spec.ts"]=1
      specs["tests/e2e/calendar-subtask-drag.spec.ts"]=1
      specs["tests/e2e/deadline-type.spec.ts"]=1
      specs["tests/e2e/list-view-ux.spec.ts"]=1
      specs["tests/e2e/project-filter.spec.ts"]=1
      specs["tests/e2e/todo-flow.spec.ts"]=1
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/routes/+page.svelte | src/routes/home/* | src/lib/components/HomeTaskItem.svelte)
      specs["tests/e2e/home-page.spec.ts"]=1
      specs["tests/e2e/deadline-type.spec.ts"]=1
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/routes/snippets/* | src/lib/stores/snippets.ts)
      specs["tests/e2e/snippets.spec.ts"]=1
      ;;
    src/routes/wiki/* | src/lib/stores/wiki.ts | src/lib/components/Wiki*.svelte | src/lib/utils/markdown.ts)
      specs["tests/e2e/wiki.spec.ts"]=1
      ;;
    src/routes/task/*)
      specs["tests/e2e/deadline-type.spec.ts"]=1
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/lib/components/SearchModal.svelte)
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/lib/components/Toasts.svelte | src/lib/stores/ui.ts)
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/lib/components/ProjectFilter.svelte | src/lib/stores/projects.ts)
      specs["tests/e2e/project-filter.spec.ts"]=1
      specs["tests/e2e/list-view-ux.spec.ts"]=1
      ;;
    src/lib/components/TaskDetailPanel.svelte)
      specs["tests/e2e/ux-improvements.spec.ts"]=1
      ;;
    src/lib/components/SubtaskList.svelte)
      specs["tests/e2e/calendar-subtask-drag.spec.ts"]=1
      ;;
    src/lib/utils/deadline.ts)
      specs["tests/e2e/deadline-type.spec.ts"]=1
      ;;
    src/lib/utils/priority.ts)
      specs["tests/e2e/list-view-ux.spec.ts"]=1
      ;;
    src/lib/utils/dates.ts)
      specs["tests/e2e/calendar-drag-drop.spec.ts"]=1
      specs["tests/e2e/calendar-expand-collapse.spec.ts"]=1
      specs["tests/e2e/calendar-subtask-drag.spec.ts"]=1
      specs["tests/e2e/home-page.spec.ts"]=1
      ;;
    src/lib/components/DueDateFilter.svelte | src/lib/components/DeadlineTypeFilter.svelte)
      specs["tests/e2e/deadline-type.spec.ts"]=1
      specs["tests/e2e/list-view-ux.spec.ts"]=1
      ;;
    *)
      # Unrecognized frontend file — run all tests to be safe
      echo "Unrecognized file triggered full test run: $file" >&2
      exit 0
      ;;
  esac
done <<< "$frontend_changes"

# Output deduplicated specs (associative array keys are already unique)
if [ ${#specs[@]} -eq 0 ]; then
  exit 0
fi

echo "${!specs[@]}"
