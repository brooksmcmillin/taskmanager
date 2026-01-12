# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

All commands should be run from `services/web-app/`:

```bash
npm run dev              # Start dev server (localhost:4321)
npm run build            # Production build
npm run preview          # Preview production build
npm test                 # Run tests (watch mode)
npm run test:run         # Run tests once (CI mode)
npm run test:ui          # Vitest UI dashboard
npm run format           # Format with Prettier
npm run format:check     # Check formatting
npm run lint             # ESLint security checks
npm run migrate:up       # Apply database migrations
npm run migrate:create   # Create new migration (generates .up.sql and .down.sql)
npm run migrate:rollback # Rollback last migration
npm run check:openapi    # Verify OpenAPI spec covers all routes
```

## Architecture Overview

**Stack**: Astro 5.x (SSR) + PostgreSQL 15 (pgvector) + Node.js 22

### Key Directories (under `services/web-app/`)

- `src/lib/` - Core libraries: database, auth, validators, error handling, API responses
- `src/pages/api/` - REST API endpoints (export GET/POST/PUT/DELETE handlers)
- `src/migrations/` - SQL migration files (timestamped pairs: `.up.sql` + `.down.sql`)
- `src/components/` - Astro components
- `tests/` - Vitest tests with mocked fetch/db in `tests/setup.js`

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

Note: Some legacy endpoints still return `{ tasks: [...] }` or raw arrays (see TODO.md).

## Configuration

Environment config is centralized in `src/lib/config.js`. Key variables:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`
- `ROOT_DOMAIN` (for production)
- `BCRYPT_ROUNDS` (default: 12)
- `SESSION_DURATION_DAYS` (default: 7)

## Docker

Root `docker-compose.yml` runs both services:
- App: Node.js on port 4321, builds from `services/web-app/`
- PostgreSQL: pgvector with SSL, port 5432, certs in `services/db/certs/`

## Pre-commit Hooks

Husky runs security checks that detect:
- Secrets (passwords, API keys, private keys)
- Dangerous patterns (eval, innerHTML)
- SQL injection patterns (string concatenation in queries)
- Critical npm vulnerabilities
