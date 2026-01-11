# Migration Plan: Astro/Node.js to FastAPI + SvelteKit

## Executive Summary

This document outlines a comprehensive migration strategy for converting the TaskManager application from its current Astro/Node.js SSR architecture to a FastAPI (Python) backend with a SvelteKit frontend. The migration preserves all existing functionality while modernizing the technology stack.

**Current Stack:** Astro 5.x + Node.js + PostgreSQL + Vanilla JS
**Target Stack:** FastAPI + SvelteKit + PostgreSQL + TypeScript

**Estimated Scope:**
- Backend: ~1,400 LOC in `src/lib/` → ~1,200 LOC Python
- API Endpoints: 16 endpoints → 16 FastAPI routes
- Frontend: 8 Astro components → 8 Svelte components
- Database: No schema changes required (reuse existing PostgreSQL)

---

## Table of Contents

1. [Phase Overview](#phase-overview)
2. [Phase 1: Backend Migration (FastAPI)](#phase-1-backend-migration-fastapi)
3. [Phase 2: Frontend Migration (SvelteKit)](#phase-2-frontend-migration-sveltekit)
4. [Phase 3: Integration & Deployment](#phase-3-integration--deployment)
5. [File Mapping Reference](#file-mapping-reference)
6. [Database Considerations](#database-considerations)
7. [Testing Strategy](#testing-strategy)
8. [Risk Mitigation](#risk-mitigation)
9. [Rollback Plan](#rollback-plan)

---

## Phase Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Backend Migration                                                   │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 1.1 Project Setup & Infrastructure                                          │
│ 1.2 Database Layer (SQLAlchemy models)                                      │
│ 1.3 Core Libraries (auth, validation, errors)                               │
│ 1.4 API Endpoints (auth, todos, projects)                                   │
│ 1.5 OAuth 2.0 Server                                                        │
│ 1.6 Backend Testing                                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Phase 2: Frontend Migration                                                  │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 2.1 SvelteKit Project Setup                                                 │
│ 2.2 Layout & Navigation Components                                          │
│ 2.3 Authentication Pages                                                    │
│ 2.4 Task Management UI                                                      │
│ 2.5 Calendar Component                                                      │
│ 2.6 OAuth Client Management                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ Phase 3: Integration & Deployment                                            │
│ ─────────────────────────────────────────────────────────────────────────── │
│ 3.1 Docker Configuration                                                    │
│ 3.2 Environment Configuration                                               │
│ 3.3 End-to-End Testing                                                      │
│ 3.4 Performance Validation                                                  │
│ 3.5 Deployment & Cutover                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Backend Migration (FastAPI)

### 1.1 Project Setup & Infrastructure

#### Directory Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry
│   ├── config.py                  # Configuration management
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py               # /api/auth/* routes
│   │   ├── todos.py              # /api/todos/* routes
│   │   ├── projects.py           # /api/projects/* routes
│   │   ├── categories.py         # /api/categories route
│   │   ├── search.py             # /api/tasks/search route
│   │   └── oauth/
│   │       ├── __init__.py
│   │       ├── authorize.py      # Authorization endpoint
│   │       ├── token.py          # Token endpoint
│   │       ├── clients.py        # Client management
│   │       └── device.py         # Device flow endpoints
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py           # Password hashing, tokens
│   │   ├── errors.py             # Error definitions
│   │   └── rate_limit.py         # Rate limiting
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py               # User model
│   │   ├── session.py            # Session model
│   │   ├── todo.py               # Todo model
│   │   ├── project.py            # Project model
│   │   └── oauth.py              # OAuth models (client, token, etc.)
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py               # Auth request/response schemas
│   │   ├── todo.py               # Todo schemas
│   │   ├── project.py            # Project schemas
│   │   └── oauth.py              # OAuth schemas
│   │
│   └── db/
│       ├── __init__.py
│       ├── database.py           # Database connection
│       └── crud.py               # CRUD operations
│
├── alembic/
│   ├── versions/                 # Migration files
│   └── env.py
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_todos.py
│   ├── test_projects.py
│   └── test_oauth.py
│
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── Dockerfile
```

#### Dependencies (requirements.txt)

```
# Core
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.12

# Database
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
alembic==1.14.0

# Security
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0

# Validation
pydantic==2.10.0
pydantic-settings==2.6.0
email-validator==2.2.0

# Rate limiting
slowapi==0.1.9

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

### 1.2 Database Layer

#### SQLAlchemy Model Mapping

| Current (db.js) | Target (SQLAlchemy) | Notes |
|-----------------|---------------------|-------|
| `TodoDB.createUser()` | `User` model + `create_user()` | bcrypt compatible |
| `TodoDB.getSession()` | `Session` model + query | 7-day expiry preserved |
| `TodoDB.getTodos()` | `Todo` model + `get_todos()` | QueryBuilder → SQLAlchemy query |
| `TodoDB.createTodo()` | `create_todo()` | JSONB tags preserved |
| `TodoDB.searchTodos()` | `search_todos()` | PostgreSQL tsvector preserved |
| OAuth methods | `OAuthClient`, `AccessToken`, etc. | Full RFC compliance |

#### Example Model: Todo

```python
# app/models/todo.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from app.db.database import Base
import enum

class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

class Status(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"

class Todo(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    priority = Column(Enum(Priority), default=Priority.medium)
    status = Column(Enum(Status), default=Status.pending)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_date = Column(DateTime(timezone=True), nullable=True)
    estimated_hours = Column(Integer, nullable=True)
    actual_hours = Column(Integer, nullable=True)
    tags = Column(JSON, default=list)
    context = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default="now()")
    updated_at = Column(DateTime(timezone=True), onupdate="now()")

    # Relationships
    project = relationship("Project", back_populates="todos")
    user = relationship("User", back_populates="todos")
```

### 1.3 Core Libraries Mapping

#### Error Handling (`src/lib/errors.js` → `app/core/errors.py`)

```python
# app/core/errors.py
from fastapi import HTTPException
from typing import Optional, Dict, Any

class ApiError(HTTPException):
    def __init__(
        self,
        code: str,
        status_code: int,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.error_details = details
        super().__init__(
            status_code=status_code,
            detail={"code": code, "message": message, "details": details}
        )

class Errors:
    @staticmethod
    def invalid_credentials():
        return ApiError("AUTH_001", 401, "Invalid username or password")

    @staticmethod
    def auth_required():
        return ApiError("AUTH_002", 401, "Authentication required")

    @staticmethod
    def session_expired():
        return ApiError("AUTH_003", 401, "Session has expired")

    # ... (map all 30+ error types from errors.js)

errors = Errors()
```

#### Validation (`src/lib/validators.js` → `app/schemas/*.py`)

Pydantic models replace manual validation:

```python
# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field, field_validator
import re

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError('Username must start with a letter')
        return v

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        checks = [
            bool(re.search(r'[a-z]', v)),
            bool(re.search(r'[A-Z]', v)),
            bool(re.search(r'[0-9]', v)),
            bool(re.search(r'[^a-zA-Z0-9]', v)),
        ]
        if sum(checks) < 2:
            raise ValueError('Password must contain at least 2 of: lowercase, uppercase, numbers, special chars')
        return v

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    message: str
    user: dict
```

#### Authentication (`src/lib/auth.js` → `app/core/security.py`)

```python
# app/core/security.py
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def generate_session_id() -> str:
    return secrets.token_hex(32)

def generate_token() -> str:
    return secrets.token_hex(32)
```

### 1.4 API Endpoints Mapping

#### Authentication Routes

| Current Endpoint | FastAPI Route | Handler |
|------------------|---------------|---------|
| `POST /api/auth/login` | `POST /api/auth/login` | `auth.login()` |
| `POST /api/auth/register` | `POST /api/auth/register` | `auth.register()` |
| `POST /api/auth/logout` | `POST /api/auth/logout` | `auth.logout()` |

```python
# app/api/auth.py
from fastapi import APIRouter, Response, Depends
from app.schemas.auth import LoginRequest, UserCreate
from app.core.security import verify_password, hash_password
from app.db.crud import get_user_by_username, create_user, create_session
from app.dependencies import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    db = Depends(get_db)
):
    user = await get_user_by_username(db, request.username)
    if not user or not verify_password(request.password, user.password_hash):
        raise errors.invalid_credentials()

    session = await create_session(db, user.id)

    # Set HTTP-only cookie (matching current behavior)
    response.set_cookie(
        key="session_id",
        value=session.id,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
        secure=settings.is_production
    )

    return {"message": "Login successful", "user": {"username": user.username}}
```

#### Todo Routes

| Current Endpoint | FastAPI Route | Handler |
|------------------|---------------|---------|
| `GET /api/todos` | `GET /api/todos` | `todos.list_todos()` |
| `POST /api/todos` | `POST /api/todos` | `todos.create_todo()` |
| `GET /api/todos/[id]` | `GET /api/todos/{id}` | `todos.get_todo()` |
| `PUT /api/todos/[id]` | `PUT /api/todos/{id}` | `todos.update_todo()` |
| `DELETE /api/todos/[id]` | `DELETE /api/todos/{id}` | `todos.delete_todo()` |
| `POST /api/todos/[id]/complete` | `POST /api/todos/{id}/complete` | `todos.complete_todo()` |

```python
# app/api/todos.py
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from app.schemas.todo import TodoCreate, TodoUpdate, TodoResponse
from app.dependencies import get_current_user, get_db

router = APIRouter(prefix="/api/todos", tags=["todos"])

@router.get("", response_model=dict)
async def list_todos(
    status: Optional[str] = Query(None),
    project_id: Optional[int] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    todos = await get_todos_filtered(
        db,
        user_id=user.id,
        status=status,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date
    )
    return {"tasks": todos, "meta": {"count": len(todos)}}
```

### 1.5 OAuth 2.0 Server

The OAuth implementation is the most complex part. Key considerations:

#### Grant Types to Implement

1. **Authorization Code** (with PKCE)
2. **Refresh Token**
3. **Client Credentials**
4. **Device Authorization** (RFC 8628)

#### Device Flow Specifics

```python
# app/api/oauth/device.py
from fastapi import APIRouter
import secrets

router = APIRouter(prefix="/api/oauth/device", tags=["oauth"])

def generate_user_code() -> str:
    """Generate user-friendly code (e.g., WDJB-MJHT)"""
    chars = 'BCDFGHJKLMNPQRSTVWXZ'  # Consonants only, no ambiguous chars
    code = ''.join(secrets.choice(chars) for _ in range(8))
    return f"{code[:4]}-{code[4:]}"

@router.post("/code")
async def device_authorization(
    client_id: str,
    scope: Optional[str] = "read",
    db = Depends(get_db)
):
    client = await get_oauth_client(db, client_id)
    if not client:
        raise errors.oauth_invalid_client()

    device_code = secrets.token_hex(32)
    user_code = generate_user_code()

    await create_device_authorization(
        db,
        device_code=device_code,
        user_code=user_code,
        client_id=client_id,
        scopes=scope.split(),
        expires_in=1800,
        interval=5
    )

    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": f"{settings.base_url}/oauth/device",
        "expires_in": 1800,
        "interval": 5
    }
```

### 1.6 Backend Testing

#### Test Structure

```
tests/
├── conftest.py          # Fixtures, test database setup
├── test_auth.py         # Auth endpoint tests
├── test_todos.py        # Todo CRUD tests
├── test_projects.py     # Project tests
├── test_oauth.py        # OAuth flow tests
└── test_device_flow.py  # Device authorization tests
```

#### Example Test

```python
# tests/test_auth.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    response = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "TestPass123!"
    })
    assert response.status_code == 200
    assert "session_id" in response.cookies
    assert response.json()["user"]["username"] == "testuser"

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "wrongpass"
    })
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_001"
```

---

## Phase 2: Frontend Migration (SvelteKit)

### 2.1 SvelteKit Project Setup

#### Directory Structure

```
frontend/
├── src/
│   ├── routes/
│   │   ├── +layout.svelte        # Root layout
│   │   ├── +layout.server.ts     # Auth check
│   │   ├── +page.svelte          # Dashboard (index)
│   │   ├── login/
│   │   │   └── +page.svelte
│   │   ├── register/
│   │   │   └── +page.svelte
│   │   ├── projects/
│   │   │   └── +page.svelte
│   │   ├── oauth-clients/
│   │   │   └── +page.svelte
│   │   └── oauth/
│   │       ├── authorize/
│   │       │   └── +page.svelte
│   │       └── device/
│   │           ├── +page.svelte
│   │           ├── success/
│   │           │   └── +page.svelte
│   │           └── denied/
│   │               └── +page.svelte
│   │
│   ├── lib/
│   │   ├── components/
│   │   │   ├── Navigation.svelte
│   │   │   ├── Modal.svelte
│   │   │   ├── TodoModal.svelte
│   │   │   ├── TodoForm.svelte
│   │   │   ├── ProjectModal.svelte
│   │   │   ├── ProjectForm.svelte
│   │   │   ├── DragDropCalendar.svelte
│   │   │   └── ThemeToggle.svelte
│   │   │
│   │   ├── stores/
│   │   │   ├── todos.ts          # Todo state management
│   │   │   ├── projects.ts       # Project state
│   │   │   ├── auth.ts           # Auth state
│   │   │   └── ui.ts             # UI state (theme, modals)
│   │   │
│   │   ├── api/
│   │   │   └── client.ts         # API client wrapper
│   │   │
│   │   └── utils/
│   │       ├── colors.ts         # Color utilities
│   │       └── dates.ts          # Date utilities
│   │
│   └── app.scss                  # Global styles (port from main.scss)
│
├── static/
│   └── favicon.svg
│
├── svelte.config.js
├── vite.config.ts
├── tsconfig.json
└── package.json
```

### 2.2 Component Mapping

| Astro Component | Svelte Component | Complexity | Notes |
|-----------------|------------------|------------|-------|
| `Layout.astro` | `+layout.svelte` | Low | SSR layout |
| `Navigation.astro` | `Navigation.svelte` | Low | Direct port |
| `ThemeToggle.astro` | `ThemeToggle.svelte` | Low | Use Svelte store |
| `Modal.astro` | `Modal.svelte` | Low | Slot-based |
| `TodoForm.astro` | `TodoForm.svelte` | Medium | Form binding |
| `TodoModal.astro` | `TodoModal.svelte` | Medium | Uses Modal + Form |
| `ProjectForm.astro` | `ProjectForm.svelte` | Medium | Form binding |
| `ProjectModal.astro` | `ProjectModal.svelte` | Medium | Uses Modal + Form |
| `DragDropCalendar.astro` | `DragDropCalendar.svelte` | High | Use svelte-dnd-action |

### 2.3 State Management

Replace `localStorage` + custom events with Svelte stores:

```typescript
// src/lib/stores/todos.ts
import { writable, derived } from 'svelte/store';
import type { Todo } from '$lib/types';
import { api } from '$lib/api/client';

function createTodoStore() {
    const { subscribe, set, update } = writable<Todo[]>([]);

    return {
        subscribe,
        load: async (filters?: TodoFilters) => {
            const todos = await api.get('/api/todos', { params: filters });
            set(todos.tasks);
        },
        add: async (todo: TodoCreate) => {
            const created = await api.post('/api/todos', todo);
            update(todos => [...todos, created]);
            return created;
        },
        update: async (id: number, updates: TodoUpdate) => {
            const updated = await api.put(`/api/todos/${id}`, updates);
            update(todos => todos.map(t => t.id === id ? updated : t));
            return updated;
        },
        complete: async (id: number) => {
            await api.post(`/api/todos/${id}/complete`);
            update(todos => todos.map(t =>
                t.id === id ? { ...t, status: 'completed' } : t
            ));
        },
        remove: async (id: number) => {
            await api.delete(`/api/todos/${id}`);
            update(todos => todos.filter(t => t.id !== id));
        }
    };
}

export const todos = createTodoStore();

// Derived stores for filtered views
export const pendingTodos = derived(todos, $todos =>
    $todos.filter(t => t.status === 'pending')
);

export const todosByProject = derived(todos, $todos => {
    const grouped: Record<number, Todo[]> = {};
    $todos.forEach(t => {
        const pid = t.project_id || 0;
        if (!grouped[pid]) grouped[pid] = [];
        grouped[pid].push(t);
    });
    return grouped;
});
```

### 2.4 Calendar Component Migration

The `DragDropCalendar.astro` (303 lines) requires careful migration:

```svelte
<!-- src/lib/components/DragDropCalendar.svelte -->
<script lang="ts">
    import { dndzone } from 'svelte-dnd-action';
    import { todos } from '$lib/stores/todos';
    import { hexTo50Shade } from '$lib/utils/colors';

    let currentWeekStart = getStartOfWeek(new Date());

    function getStartOfWeek(date: Date): Date {
        const d = new Date(date);
        const day = d.getDay();
        d.setDate(d.getDate() - day);
        return d;
    }

    function generateDays(start: Date, count: number) {
        return Array.from({ length: count }, (_, i) => {
            const date = new Date(start);
            date.setDate(date.getDate() + i);
            return {
                date,
                dateStr: date.toISOString().split('T')[0],
                isToday: date.toDateString() === new Date().toDateString()
            };
        });
    }

    $: days = generateDays(currentWeekStart, 21);

    $: todosByDate = $todos.reduce((acc, todo) => {
        if (todo.due_date) {
            const dateStr = todo.due_date.split('T')[0];
            if (!acc[dateStr]) acc[dateStr] = [];
            acc[dateStr].push({ ...todo, id: todo.id });
        }
        return acc;
    }, {} as Record<string, typeof $todos>);

    async function handleDrop(dateStr: string, event: CustomEvent) {
        const { items } = event.detail;
        const movedTodo = items[0];
        if (movedTodo) {
            await todos.update(movedTodo.id, { due_date: dateStr });
        }
    }

    function prevWeek() {
        currentWeekStart = new Date(currentWeekStart);
        currentWeekStart.setDate(currentWeekStart.getDate() - 7);
    }

    function nextWeek() {
        currentWeekStart = new Date(currentWeekStart);
        currentWeekStart.setDate(currentWeekStart.getDate() + 7);
    }
</script>

<div class="card" id="drag-drop-calendar">
    <div class="flex justify-between items-center mb-6">
        <h2 class="text-xl font-semibold">Task Calendar</h2>
        <div class="flex gap-4">
            <button class="btn btn-secondary btn-sm" on:click={prevWeek}>
                ← Previous
            </button>
            <button class="btn btn-secondary btn-sm" on:click={nextWeek}>
                Next →
            </button>
        </div>
    </div>

    <div id="calendar-container">
        <div class="calendar-headers">
            {#each ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'] as day}
                <div class="calendar-header-day">{day}</div>
            {/each}
        </div>

        <div id="calendar-grid">
            {#each days as { date, dateStr, isToday }}
                <div
                    class="calendar-day"
                    class:today={isToday}
                    data-date={dateStr}
                    use:dndzone={{
                        items: todosByDate[dateStr] || [],
                        dropTargetStyle: { outline: '2px dashed #3b82f6' }
                    }}
                    on:consider={(e) => handleDrop(dateStr, e)}
                    on:finalize={(e) => handleDrop(dateStr, e)}
                >
                    <div class="calendar-date">
                        {date.getMonth() + 1}/{date.getDate()}
                    </div>
                    <div class="tasks-container">
                        {#each todosByDate[dateStr] || [] as todo (todo.id)}
                            <div
                                class="calendar-task {todo.priority}-priority"
                                style="background-color: {hexTo50Shade(todo.project_color || '#6b7280')};
                                       border-left: 4px solid {todo.project_color || '#6b7280'}"
                                on:dblclick={() => openEditModal(todo)}
                            >
                                <div class="task-title">{todo.title}</div>
                            </div>
                        {/each}
                    </div>
                </div>
            {/each}
        </div>
    </div>
</div>
```

### 2.5 API Client

```typescript
// src/lib/api/client.ts
import { browser } from '$app/environment';
import { goto } from '$app/navigation';

const BASE_URL = import.meta.env.VITE_API_URL || '';

class ApiClient {
    private async request<T>(
        method: string,
        path: string,
        options: { body?: unknown; params?: Record<string, string> } = {}
    ): Promise<T> {
        const url = new URL(`${BASE_URL}${path}`, window.location.origin);

        if (options.params) {
            Object.entries(options.params).forEach(([key, value]) => {
                if (value) url.searchParams.set(key, value);
            });
        }

        const response = await fetch(url.toString(), {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: options.body ? JSON.stringify(options.body) : undefined,
        });

        if (response.status === 401) {
            if (browser) goto('/login');
            throw new Error('Authentication required');
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || 'Request failed');
        }

        return response.json();
    }

    get<T>(path: string, options?: { params?: Record<string, string> }) {
        return this.request<T>('GET', path, options);
    }

    post<T>(path: string, body?: unknown) {
        return this.request<T>('POST', path, { body });
    }

    put<T>(path: string, body?: unknown) {
        return this.request<T>('PUT', path, { body });
    }

    delete<T>(path: string) {
        return this.request<T>('DELETE', path);
    }
}

export const api = new ApiClient();
```

---

## Phase 3: Integration & Deployment

### 3.1 Docker Configuration

#### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:22-alpine

WORKDIR /app
COPY --from=builder /app/build ./build
COPY --from=builder /app/package*.json ./
RUN npm ci --omit=dev

RUN adduser -D appuser
USER appuser

EXPOSE 3000

CMD ["node", "build"]
```

#### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://backend:8000
    depends_on:
      - backend

  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}

volumes:
  postgres_data:
```

### 3.2 Environment Variables

#### Backend (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/taskmanager

# Security
SECRET_KEY=your-secret-key-here
BCRYPT_ROUNDS=12

# Session
SESSION_EXPIRY_DAYS=7
SESSION_COOKIE_NAME=session_id

# OAuth
OAUTH_TOKEN_EXPIRY=3600
OAUTH_DEVICE_CODE_EXPIRY=1800

# Rate Limiting
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_WINDOW_MINUTES=15

# Environment
ENVIRONMENT=development
DEBUG=true
```

#### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000
PUBLIC_APP_NAME=TaskManager
```

### 3.3 Migration Checklist

#### Pre-Migration
- [ ] Back up existing PostgreSQL database
- [ ] Document current API response formats
- [ ] Inventory all environment variables
- [ ] Set up staging environment

#### Backend Migration
- [ ] Set up FastAPI project structure
- [ ] Implement SQLAlchemy models
- [ ] Create Alembic migrations (or reuse existing schema)
- [ ] Port all 16 API endpoints
- [ ] Implement OAuth 2.0 server
- [ ] Port rate limiting logic
- [ ] Write and pass all backend tests
- [ ] Validate bcrypt password compatibility

#### Frontend Migration
- [ ] Set up SvelteKit project
- [ ] Port SCSS styles
- [ ] Implement all 8 components
- [ ] Set up Svelte stores
- [ ] Implement API client
- [ ] Test all user flows
- [ ] Validate drag-drop calendar

#### Integration
- [ ] Configure Docker Compose
- [ ] Set up environment variables
- [ ] Run end-to-end tests
- [ ] Performance benchmarking
- [ ] Security audit

---

## File Mapping Reference

### Backend File Mapping

| Source (Node.js) | Target (Python) | LOC |
|------------------|-----------------|-----|
| `src/lib/db.js` | `app/models/*.py` + `app/db/crud.py` | ~800 |
| `src/lib/auth.js` | `app/core/security.py` | ~100 |
| `src/lib/errors.js` | `app/core/errors.py` | ~150 |
| `src/lib/validators.js` | `app/schemas/*.py` | ~200 |
| `src/lib/config.js` | `app/config.py` | ~80 |
| `src/lib/rateLimit.js` | `app/core/rate_limit.py` | ~50 |
| `src/lib/apiResponse.js` | (Built into FastAPI) | 0 |
| `src/middleware.js` | `app/dependencies.py` | ~100 |
| `src/pages/api/auth/*.js` | `app/api/auth.py` | ~150 |
| `src/pages/api/todos*.js` | `app/api/todos.py` | ~200 |
| `src/pages/api/projects*.js` | `app/api/projects.py` | ~150 |
| `src/pages/api/oauth/*.js` | `app/api/oauth/*.py` | ~300 |

### Frontend File Mapping

| Source (Astro) | Target (Svelte) | Notes |
|----------------|-----------------|-------|
| `src/layouts/Layout.astro` | `src/routes/+layout.svelte` | Root layout |
| `src/pages/index.astro` | `src/routes/+page.svelte` | Dashboard |
| `src/pages/login.astro` | `src/routes/login/+page.svelte` | Login form |
| `src/pages/register.astro` | `src/routes/register/+page.svelte` | Registration |
| `src/pages/projects.astro` | `src/routes/projects/+page.svelte` | Projects page |
| `src/pages/oauth-clients.astro` | `src/routes/oauth-clients/+page.svelte` | OAuth management |
| `src/pages/oauth/*.astro` | `src/routes/oauth/**/*.svelte` | OAuth flows |
| `src/components/*.astro` | `src/lib/components/*.svelte` | All components |
| `src/styles/main.scss` | `src/app.scss` | Global styles |

### Test File Mapping

| Source (Vitest) | Target (Pytest) |
|-----------------|-----------------|
| `tests/api.test.js` | `tests/test_todos.py` + `tests/test_projects.py` |
| `tests/device-oauth.test.js` | `tests/test_device_flow.py` |
| `tests/middleware.test.js` | `tests/test_auth.py` |
| `tests/pages.test.js` | (E2E tests with Playwright) |
| `tests/todos-api.test.js` | `tests/test_todos.py` |

---

## Database Considerations

### Schema Compatibility

The existing PostgreSQL schema is **fully compatible** with SQLAlchemy. No migrations needed for:

- Table structures
- Column types (including JSONB, TIMESTAMP WITH TIME ZONE)
- Indexes (including full-text search)
- Foreign keys and constraints

### Full-Text Search

Preserve PostgreSQL tsvector search:

```python
from sqlalchemy import func

async def search_todos(db, user_id: int, query: str, category: str = None):
    stmt = select(Todo).where(
        Todo.user_id == user_id,
        func.to_tsvector('english', Todo.title + ' ' + func.coalesce(Todo.description, '')).match(
            func.plainto_tsquery('english', query)
        )
    )
    if category:
        stmt = stmt.join(Project).where(Project.name == category)

    result = await db.execute(stmt)
    return result.scalars().all()
```

### bcrypt Compatibility

Python's `passlib` with bcrypt backend is **fully compatible** with Node.js `bcryptjs` hashes:

```python
# Verify existing hashes work
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# This will verify hashes created by bcryptjs
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)  # Works with bcryptjs hashes!
```

---

## Testing Strategy

### Unit Tests (Backend)

```
pytest tests/ -v --cov=app --cov-report=html
```

Coverage targets:
- API endpoints: 90%+
- Core utilities: 95%+
- OAuth flows: 95%+

### Integration Tests

Test complete flows:
1. User registration → login → create todo → complete
2. OAuth authorization code flow with PKCE
3. Device authorization grant flow
4. Rate limiting behavior

### E2E Tests (Frontend)

Use Playwright:

```typescript
// tests/e2e/todo-flow.spec.ts
import { test, expect } from '@playwright/test';

test('create and complete todo', async ({ page }) => {
    await page.goto('/login');
    await page.fill('[name=username]', 'testuser');
    await page.fill('[name=password]', 'TestPass123!');
    await page.click('button[type=submit]');

    await expect(page).toHaveURL('/');

    // Create todo
    await page.click('[data-testid=add-todo]');
    await page.fill('[name=title]', 'Test Task');
    await page.click('[data-testid=save-todo]');

    await expect(page.locator('.task-title')).toContainText('Test Task');
});
```

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| bcrypt hash incompatibility | Low | Critical | Test early with real hashes |
| OAuth flow differences | Medium | High | Comprehensive OAuth test suite |
| Date/timezone bugs | Medium | Medium | Port exact UTC handling logic |
| Full-text search differences | Low | Medium | Test with real queries |
| Session cookie handling | Low | High | Match exact cookie attributes |
| Rate limiting bypass | Low | Medium | Port exact rate limit logic |
| Drag-drop calendar issues | Medium | Medium | Use svelte-dnd-action library |

---

## Rollback Plan

### Phase 1 Rollback (Backend Only)
- Keep Astro frontend pointing to original Node.js backend
- No user-facing changes until Phase 2 complete

### Phase 2 Rollback (Full Stack)
- Maintain original Astro app in separate branch
- DNS/load balancer switch back to original
- Database schema unchanged, so no data migration needed

### Blue-Green Deployment
1. Deploy new stack to staging
2. Run parallel with production (read-only sync)
3. Cut over DNS with instant rollback capability
4. Monitor for 48 hours before decommissioning old stack

---

## Success Criteria

1. **Functional Parity**: All 16 API endpoints return identical responses
2. **OAuth Compliance**: All 4 grant types work identically
3. **Performance**: Response times within 10% of original
4. **Test Coverage**: 90%+ backend, 80%+ frontend
5. **Zero Downtime**: Migration with no user-visible interruption
6. **Password Compatibility**: All existing users can log in

---

## Next Steps

1. **Immediate**: Set up FastAPI project structure
2. **Week 1-2**: Implement database models and core libraries
3. **Week 2-3**: Port all API endpoints
4. **Week 3-4**: Implement and test OAuth server
5. **Week 4-5**: Set up SvelteKit and port components
6. **Week 5-6**: Integration testing and deployment prep

---

*Document Version: 1.0*
*Created: 2026-01-11*
*Last Updated: 2026-01-11*
