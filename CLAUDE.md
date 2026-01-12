# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TaskManager is a monorepo containing:
- **Web Application** (`services/web-app/`) - Astro-based task management UI with REST API
- **MCP Auth Server** (`services/mcp-auth/`) - OAuth 2.0 authorization server for MCP
- **MCP Resource Server** (`services/mcp-resource/`) - MCP tools for AI assistants
- **Python SDK** (`packages/taskmanager-sdk/`) - Client library for TaskManager API

## Quick Commands

From the project root, use the Makefile:

```bash
make help            # Show all available commands
make install         # Install all dependencies
make test            # Run all tests
make lint            # Run all linting
make format          # Auto-format all code
make docker-up       # Start all Docker services
make migrate         # Run database migrations
make pre-commit      # Run pre-commit hooks on all files
```

## Build and Development Commands

### Web App (`services/web-app/`)

```bash
npm run dev              # Start dev server (localhost:4321)
npm run build            # Production build
npm run preview          # Preview production build
npm test                 # Run tests (watch mode)
npm run test:run         # Run tests once (CI mode)
npm run format           # Format with Prettier
npm run lint             # ESLint security checks
npm run migrate:up       # Apply database migrations
npm run migrate:create   # Create new migration
npm run check:openapi    # Verify OpenAPI spec covers all routes
```

### Python Services (`services/mcp-auth/`, `services/mcp-resource/`, `packages/taskmanager-sdk/`)

```bash
uv sync                  # Install dependencies
uv run pytest tests/ -v  # Run tests
uv run ruff check .      # Lint code
uv run ruff format .     # Format code
uv run pyright           # Type checking
```

## Architecture Overview

**Stack**:
- Web App: Astro 5.x (SSR) + Node.js 22
- MCP Servers: Python 3.13 + FastAPI/Starlette
- Database: PostgreSQL 15 (pgvector)
- Package Manager: npm (Node.js), uv (Python)

### Project Structure

```
taskmanager/
├── services/
│   ├── web-app/           # Astro web application
│   │   ├── src/
│   │   │   ├── lib/       # Core libraries (db, auth, validators)
│   │   │   ├── pages/api/ # REST API endpoints
│   │   │   └── migrations/# SQL migration files
│   │   └── tests/
│   ├── mcp-auth/          # OAuth 2.0 authorization server
│   │   ├── mcp_auth/      # Python package
│   │   └── tests/
│   ├── mcp-resource/      # MCP resource server
│   │   ├── mcp_resource/  # Python package
│   │   └── tests/
│   └── db/                # Database configuration
├── packages/
│   └── taskmanager-sdk/   # Python SDK
│       ├── taskmanager_sdk/
│       └── tests/
├── docker-compose.yml     # All services
├── Makefile               # Development commands
└── .pre-commit-config.yaml
```

### Core Patterns

**Database queries** - Use QueryBuilder from `src/lib/db.js` for SQL injection prevention:
```javascript
const qb = new QueryBuilder();
qb.where('user_id', userId).whereIf(status, 'status', status);
const { rows } = await query(`SELECT * FROM todos ${qb.build()}`, qb.values);
```

**API endpoints** - Standard pattern in `src/pages/api/`:
```javascript
export const POST = async ({ request }) => {
  const session = await requireAuth(request);  // From src/lib/auth.js
  const validation = validateRequired(value, 'Field');
  if (!validation.valid) return validation.error.toResponse();
  const data = await TodoDB.createTodo(...);   // From src/lib/db.js
  return createdResponse(data);                // From src/lib/apiResponse.js
};
```

**Error handling** - Use standardized errors from `src/lib/errors.js`:
```javascript
import { errors } from '../lib/errors.js';
return errors.notFound('Todo').toResponse();
return errors.authRequired().toResponse();
```

**Input validation** - Use validators from `src/lib/validators.js`:
- `validateRequired()`, `validateEmail()`, `validatePassword()`, `validateLength()`, `validateId()`

**Authentication**:
- Session-based: `requireAuth(request)` returns session with user data
- OAuth: Bearer tokens in Authorization header, validated via `validateBearerToken()`
- User available in Astro pages via `context.locals.user`

### Response Formats

```javascript
// Success (list): { data: [...], meta: { count } }
// Success (single): { data: {...} }
// Created: { data: {...} } with 201 status
// Error: { error: { code, message, details? } }
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure. Key variables:

**Database:**
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`

**Web App:**
- `ROOT_DOMAIN` (for production)
- `BCRYPT_ROUNDS` (default: 12)
- `SESSION_DURATION_DAYS` (default: 7)

**MCP Servers:**
- `TASKMANAGER_CLIENT_ID`, `TASKMANAGER_CLIENT_SECRET` - OAuth credentials
- `MCP_AUTH_SERVER`, `TASKMANAGER_OAUTH_HOST` - Internal service URLs
- `MCP_AUTH_SERVER_PUBLIC_URL`, `MCP_SERVER_URL` - Public URLs

## Docker

Root `docker-compose.yml` runs all services:
- **app**: Web application on port 4321
- **postgres_db**: PostgreSQL with SSL on port 5432
- **mcp-auth**: OAuth authorization server on port 9000
- **mcp-resource**: MCP resource server on port 8001

```bash
docker compose up -d           # Start all services
docker compose logs -f         # View logs
docker compose build           # Rebuild images
docker compose down            # Stop services
```

Build contexts use project root to access shared packages (SDK).

## Pre-commit Hooks

Uses the `pre-commit` package for unified hooks across Python and Node.js:

```bash
pip install pre-commit
pre-commit install
```

Hooks include:
- **General**: trailing whitespace, YAML/JSON/TOML validation, secret detection
- **Python**: ruff (lint + format), pyright (type checking), bandit (security)
- **Node.js**: eslint, prettier
- **Docker**: hadolint

## CI/CD Workflows

- `.github/workflows/test.yml` - Node.js tests and OpenAPI validation
- `.github/workflows/python-ci.yml` - Python tests for MCP services and SDK
- `.github/workflows/python-precommit.yml` - Python linting on PRs
- `.github/workflows/security.yml` - Security scanning

## Testing

```bash
# All tests
make test

# Individual services
make test-web          # Web app (Vitest)
make test-mcp-auth     # MCP auth (pytest)
make test-mcp-resource # MCP resource (pytest)
make test-sdk          # Python SDK (pytest)
```

## Python Development Notes

- Use `uv` for package management (not pip directly)
- Type hints required for all functions
- Use built-in types (`list`, `dict`) instead of `typing.List`, `typing.Dict`
- Use `| None` instead of `Optional[T]`
- Run `uv run` to execute commands in the virtual environment
