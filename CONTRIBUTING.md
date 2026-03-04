# Contributing to TaskManager

Thank you for your interest in contributing to TaskManager. This document covers the development workflow, coding standards, and expectations for pull requests.

## Table of Contents

- [Pre-commit Setup](#pre-commit-setup)
- [Branch Naming Conventions](#branch-naming-conventions)
- [Test Requirements](#test-requirements)
- [PR Checklist](#pr-checklist)

---

## Pre-commit Setup

TaskManager uses [pre-commit](https://pre-commit.com/) to enforce consistent code quality across all languages in the monorepo.

### Installation

```bash
pip install pre-commit
pre-commit install
```

This installs the git hooks that run automatically before each commit.

### What the hooks check

- **General**: trailing whitespace, YAML/JSON/TOML validation, secret detection
- **Python**: ruff (lint + format), pyright (type checking), bandit (security scanning)
- **Node.js**: eslint, prettier
- **Docker**: hadolint

### Running hooks manually

```bash
# Run on all files (useful before first commit or after hook updates)
pre-commit run --all-files

# Or via the Makefile shortcut
make pre-commit
```

### Bypassing hooks (discouraged)

Hooks should not be bypassed unless there is a specific, documented reason. If a hook is failing, investigate and fix the root cause. Do not use `--no-verify`.

---

## Branch Naming Conventions

Branch names should follow this format:

```
<type>/<short-description>
```

### Types

| Type | When to use |
|------|-------------|
| `feat/` | New features or capabilities |
| `fix/` | Bug fixes |
| `chore/` | Maintenance, refactoring, tooling updates |
| `docs/` | Documentation-only changes |
| `test/` | Test additions or improvements |
| `ci/` | CI/CD configuration changes |

### Examples

```
feat/add-wiki-search
fix/session-expiry-bug
chore/update-dependencies
docs/api-reference
test/auth-edge-cases
ci/add-lint-step
```

Branch names should use lowercase letters, numbers, and hyphens only. Keep the description concise (3-5 words).

---

## Test Requirements

**Unit tests are required for all new features and bug fixes.** Tests must be written before creating a PR or commit.

### What to test

- **Happy path**: the primary expected behavior
- **Edge cases**: boundary conditions, empty inputs, large values
- **Authorization**: verify that users cannot access or modify other users' data
- **Error cases**: invalid input, missing resources, permission denied

### Backend tests (FastAPI + pytest)

Tests live in `services/backend/tests/`. Run them with:

```bash
cd services/backend
uv run pytest tests/ -v
```

For a specific test file:

```bash
uv run pytest tests/test_todos.py -v
```

Stop at first failure:

```bash
uv run pytest tests/ -x -v
```

### Frontend tests (Playwright)

Tests live in `services/frontend/tests/`. Run them with:

```bash
cd services/frontend
npm test
```

### MCP service and SDK tests

Each service has its own test suite:

```bash
cd services/mcp-auth && uv run pytest tests/ -v
cd services/mcp-resource && uv run pytest tests/ -v
cd packages/taskmanager-sdk && uv run pytest tests/ -v
```

### Running all tests from the root

```bash
make test
```

### Test must pass before PR

CI runs all tests automatically. Do not open a PR with known test failures.

---

## PR Checklist

Before opening a pull request, verify the following:

### Code quality

- [ ] All new functions and methods have type hints (Python)
- [ ] Python uses built-in types (`list`, `dict`) not `typing.List`, `typing.Dict`
- [ ] Python uses `X | None` instead of `Optional[X]`
- [ ] No dead code or unused imports introduced
- [ ] No secrets, credentials, or environment-specific values committed

### Tests

- [ ] New tests written for all new features and bug fixes
- [ ] All existing tests pass locally (`make test` or per-service commands)
- [ ] Tests cover the happy path, edge cases, and authorization checks

### Linting and formatting

- [ ] Ruff lint passes: `cd services/backend && uv run ruff check .`
- [ ] Ruff format passes: `cd services/backend && uv run ruff format --check .`
- [ ] Pyright type checking passes: `cd services/backend && uv run pyright`
- [ ] Frontend lint passes: `cd services/frontend && npm run lint`
- [ ] Pre-commit hooks pass: `pre-commit run --all-files`

### PR description

- [ ] PR title follows `<type>(<scope>): <short description>` format (e.g., `feat(wiki): add full-text search`)
- [ ] Description explains **what** changed and **why**
- [ ] Related task URL included if applicable (e.g., `Task: https://todo.brooksmcmillin.com/task/123`)
- [ ] Breaking changes documented if any

### Review

- [ ] Self-reviewed the diff before marking ready for review
- [ ] CI is green (all checks pass)
- [ ] Addressed all review comments before requesting re-review
