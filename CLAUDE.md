# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TaskManager is a monorepo containing:

- **Frontend** (`services/frontend/`) - SvelteKit 5.0 task management UI with TypeScript
- **Backend** (`services/backend/`) - FastAPI REST API with SQLAlchemy (async) + PostgreSQL
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

### Frontend (`services/frontend/`) - SvelteKit

```bash
npm run dev              # Start dev server (localhost:5173)
npm run build            # Production build
npm run preview          # Preview production build
npm test                 # Run E2E tests with Playwright
npm run test:ui          # Run tests in UI mode
npm run format           # Format with Prettier
npm run lint             # Lint with Prettier
npm run check            # SvelteKit type checking
```

### Backend (`services/backend/`) - FastAPI

```bash
uv sync                          # Install dependencies
uv run uvicorn app.main:app --reload  # Start dev server (localhost:8000)
uv run pytest tests/ -v          # Run tests
uv run ruff check .              # Lint code
uv run ruff format .             # Format code
uv run pyright                   # Type checking
uv run alembic upgrade head      # Run database migrations
uv run alembic revision --autogenerate -m "description"  # Create migration
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

- Frontend: SvelteKit 5.0 + TypeScript + Vite
- Backend: FastAPI + SQLAlchemy (async) + Python 3.12+
- Database: PostgreSQL 15 (pgvector)
- MCP Servers: Python 3.13 + FastAPI/Starlette
- Package Manager: npm (Node.js), uv (Python)

### Project Structure

```
taskmanager/
├── services/
│   ├── frontend/          # SvelteKit frontend
│   │   ├── src/
│   │   │   ├── routes/    # SvelteKit pages
│   │   │   ├── lib/       # Components, stores, API client
│   │   │   └── app.scss   # Global styles
│   │   └── tests/         # Playwright E2E tests
│   ├── backend/           # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/       # API route handlers
│   │   │   ├── core/      # Security, errors, rate limiting
│   │   │   ├── models/    # SQLAlchemy models
│   │   │   ├── schemas/   # Pydantic request/response schemas
│   │   │   └── db/        # Database connection & utilities
│   │   ├── alembic/       # Database migrations
│   │   └── tests/         # pytest unit tests
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
├── docs/                  # Documentation
├── docker-compose.yml     # All services
├── Makefile               # Development commands
└── .pre-commit-config.yaml
```

### Core Patterns

#### Backend (FastAPI)

**API endpoints** - Standard pattern in `app/api/`:
```python
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.schemas.todo import TodoCreate, TodoResponse
from app.core.errors import errors

router = APIRouter(prefix="/api/todos", tags=["todos"])

@router.post("", response_model=TodoResponse, status_code=201)
async def create_todo(
    todo: TodoCreate,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    return await crud.create_todo(db, user_id=user.id, **todo.dict())
```

**Error handling** - Use standardized errors from `app/core/errors.py`:
```python
from app.core.errors import errors
raise errors.not_found('Todo')
raise errors.auth_required()
```

**Database queries** - Use SQLAlchemy ORM with async/await:
```python
from sqlalchemy import select
from app.models.todo import Todo

async def get_todos(db, user_id: int, status: str | None = None):
    stmt = select(Todo).where(Todo.user_id == user_id)
    if status:
        stmt = stmt.where(Todo.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()
```

**Input validation** - Pydantic schemas in `app/schemas/`:
```python
from pydantic import BaseModel, EmailStr, Field

class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: str = Field(default="medium")
    due_date: str | None = None
```

**Authentication**:
- Session-based: `get_current_user` dependency returns user from session cookie
- OAuth: Bearer tokens validated via `get_current_user_oauth` dependency
- Rate limiting on auth endpoints via `slowapi`

#### Frontend (SvelteKit)

**API Client** - Use centralized client from `src/lib/api/client.ts`:
```typescript
import { api } from '$lib/api/client';

// GET request with query params
const todos = await api.get('/api/todos', { params: { status: 'pending' } });

// POST request with body
const newTodo = await api.post('/api/todos', { title: 'New task' });
```

**State Management** - Use Svelte stores from `src/lib/stores/`:
```typescript
import { todos } from '$lib/stores/todos';

// Load todos
await todos.load({ status: 'pending' });

// Subscribe to changes
$: filteredTodos = $todos.filter(t => t.status === 'pending');
```

**Component Patterns** - Svelte 5 runes and reactivity:
```svelte
<script lang="ts">
  import { todos } from '$lib/stores/todos';

  let showModal = $state(false);

  async function handleSubmit(todo: TodoCreate) {
    await todos.add(todo);
    showModal = false;
  }
</script>
```

### Response Formats

**Success responses:**
```json
// List/Collection: { "data": [...], "meta": { "count": 10 } }
// Single resource: { "data": { "id": 1, "title": "...", ... } }
// Actions (delete/complete): { "data": { "deleted": true, "id": 1 } }
```

**Error responses:**
```json
{
  "detail": {
    "code": "AUTH_001",
    "message": "Invalid credentials",
    "details": { ... }
  }
}
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure. Key variables:

**Database:**
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`

**Backend:**
- `ROOT_DOMAIN` (for production)
- `BCRYPT_ROUNDS` (default: 12)
- `SESSION_DURATION_DAYS` (default: 7)
- `SECRET_KEY` (for JWT signing)
- `FRONTEND_URL` (frontend URL for CORS)

**MCP Servers:**
- `TASKMANAGER_CLIENT_ID`, `TASKMANAGER_CLIENT_SECRET` - OAuth credentials
- `MCP_AUTH_SERVER`, `TASKMANAGER_OAUTH_HOST` - Internal service URLs
- `MCP_AUTH_SERVER_PUBLIC_URL`, `MCP_SERVER_URL` - Public URLs

## Docker

Root `docker-compose.yml` runs all services:

- **frontend**: SvelteKit app on port 3000
- **backend**: FastAPI on port 8000
- **postgres**: PostgreSQL with SSL on port 5432
- **mcp-auth**: OAuth authorization server on port 9000
- **mcp-resource**: MCP resource server on port 8001

```bash
docker compose up -d           # Start all services
docker compose logs -f         # View logs
docker compose logs -f backend frontend  # View specific services
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

- `.github/workflows/test.yml` - Main CI workflow (backend and frontend tests)
- `.github/workflows/backend-ci.yml` - Backend tests (FastAPI + pytest)
- `.github/workflows/frontend-ci.yml` - Frontend tests (SvelteKit + Playwright)
- `.github/workflows/python-ci.yml` - Python tests for MCP services and SDK
- `.github/workflows/security.yml` - Security scanning

## Testing

```bash
# All tests
make test

# Individual services
make test-frontend     # SvelteKit (Playwright)
make test-backend      # FastAPI (pytest)
make test-mcp-auth     # MCP auth (pytest)
make test-mcp-resource # MCP resource (pytest)
make test-sdk          # Python SDK (pytest)
```

**Backend Testing** (FastAPI):
- Unit tests with pytest
- Async test support via pytest-asyncio
- Test client via httpx AsyncClient
- Test database fixtures in conftest.py

**Frontend Testing** (SvelteKit):
- E2E tests with Playwright
- Component testing with Svelte Testing Library
- Test specs in `tests/` directory

## Python Development Notes

- Use `uv` for package management (not pip directly)
- Type hints required for all functions
- Use built-in types (`list`, `dict`) instead of `typing.List`, `typing.Dict`
- Use `| None` instead of `Optional[T]`
- Run `uv run` to execute commands in the virtual environment
