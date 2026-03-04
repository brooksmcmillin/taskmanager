# TaskManager Backend

FastAPI backend for TaskManager application.

## Stack

- **FastAPI** - Web framework
- **SQLAlchemy** (async) - ORM
- **PostgreSQL 15** with pgvector - Database
- **Alembic** - Database migrations
- **Pydantic** - Input validation and serialization
- **Python 3.12+** - Runtime

## Development

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type checking
uv run pyright
```

## Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

## API Endpoints

### Authentication (`/api/auth`)

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - End session
- `GET /api/auth/session` - Check session validity
- `GET /api/auth/me` - Get current user profile
- `PUT /api/auth/email` - Update email address
- `PUT /api/auth/password` - Change password

### WebAuthn / Passkeys (`/api/auth/webauthn`)

- `POST /api/auth/webauthn/register/options` - Get passkey registration options
- `POST /api/auth/webauthn/register/verify` - Complete passkey registration
- `POST /api/auth/webauthn/authenticate/options` - Get authentication challenge
- `POST /api/auth/webauthn/authenticate/verify` - Verify passkey assertion
- `GET /api/auth/webauthn/credentials` - List registered passkeys
- `DELETE /api/auth/webauthn/credentials/{credential_id}` - Remove passkey

### GitHub OAuth (`/api/auth/github`)

- `GET /api/auth/github/config` - GitHub OAuth configuration
- `GET /api/auth/github/authorize` - Initiate GitHub OAuth flow
- `GET /api/auth/github/callback` - GitHub OAuth callback
- `GET /api/auth/github/providers` - List linked OAuth providers
- `DELETE /api/auth/github/disconnect` - Unlink GitHub account

### OAuth 2.0 Server (`/api/oauth`)

- `GET /api/oauth/authorize` - Authorization endpoint (display consent)
- `POST /api/oauth/authorize` - Authorization endpoint (grant/deny)
- `POST /api/oauth/token` - Token endpoint (authorization code, refresh)
- `POST /api/oauth/revoke` - Revoke token
- `GET /api/oauth/verify` - Verify token
- `GET /api/oauth/clients` - List OAuth clients
- `GET /api/oauth/clients/{client_id}/info` - Get client info
- `POST /api/oauth/clients` - Create OAuth client
- `PUT /api/oauth/clients/{client_id}` - Update client
- `DELETE /api/oauth/clients/{client_id}` - Delete client
- `POST /api/oauth/clients/system` - Create system client (admin)
- `POST /api/oauth/device/code` - Device authorization request
- `GET /api/oauth/device/lookup` - Look up device code
- `POST /api/oauth/device/authorize` - Authorize device

### Tasks / Todos (`/api/todos`)

- `GET /api/todos` - List tasks (filtering, pagination)
- `POST /api/todos` - Create task
- `POST /api/todos/batch` - Batch create tasks
- `GET /api/todos/{todo_id}` - Get task
- `PUT /api/todos/{todo_id}` - Update task
- `PUT /api/todos` - Batch update tasks
- `DELETE /api/todos/{todo_id}` - Delete task (soft)
- `POST /api/todos/{todo_id}/complete` - Mark task complete
- `POST /api/todos/reorder` - Reorder tasks
- `GET /api/todos/{todo_id}/subtasks` - List subtasks
- `POST /api/todos/{todo_id}/subtasks` - Create subtask
- `GET /api/todos/{todo_id}/dependencies` - List dependencies
- `POST /api/todos/{todo_id}/dependencies` - Add dependency
- `DELETE /api/todos/{todo_id}/dependencies/{dependency_id}` - Remove dependency
- `GET /api/todos/{todo_id}/attachments` - List attachments
- `POST /api/todos/{todo_id}/attachments` - Upload attachment
- `GET /api/todos/{todo_id}/attachments/{attachment_id}` - Download attachment
- `DELETE /api/todos/{todo_id}/attachments/{attachment_id}` - Delete attachment
- `GET /api/todos/{todo_id}/comments` - List comments
- `POST /api/todos/{todo_id}/comments` - Add comment
- `PUT /api/todos/{todo_id}/comments/{comment_id}` - Edit comment
- `DELETE /api/todos/{todo_id}/comments/{comment_id}` - Delete comment
- `GET /api/todos/{todo_id}/wiki-pages` - List linked wiki pages

### Search (`/api/tasks`, `/api/search`)

- `GET /api/tasks/search` - Search tasks (legacy)
- `GET /api/search` - Unified search across tasks, wiki, snippets

### Projects (`/api/projects`)

- `GET /api/projects` - List projects
- `POST /api/projects` - Create project
- `GET /api/projects/{project_id}` - Get project
- `GET /api/projects/{project_id}/stats` - Project statistics
- `PUT /api/projects/{project_id}` - Update project
- `DELETE /api/projects/{project_id}` - Delete project
- `POST /api/projects/{project_id}/archive` - Archive project
- `POST /api/projects/{project_id}/unarchive` - Unarchive project
- `POST /api/projects/reorder` - Reorder projects

### Recurring Tasks (`/api/recurring-tasks`)

- `GET /api/recurring-tasks` - List recurring task templates
- `POST /api/recurring-tasks` - Create template
- `GET /api/recurring-tasks/{task_id}` - Get template
- `PUT /api/recurring-tasks/{task_id}` - Update template
- `DELETE /api/recurring-tasks/{task_id}` - Delete template

### Wiki (`/api/wiki`)

- `GET /api/wiki` - List wiki pages
- `POST /api/wiki` - Create wiki page
- `GET /api/wiki/resolve` - Resolve page by slug
- `GET /api/wiki/tree` - Get hierarchical page tree
- `GET /api/wiki/{slug_or_id}` - Get wiki page
- `PUT /api/wiki/{page_id}` - Update wiki page
- `DELETE /api/wiki/{page_id}` - Delete wiki page
- `PATCH /api/wiki/{page_id}/move` - Move/reparent page
- `GET /api/wiki/{page_id}/revisions` - List revisions
- `GET /api/wiki/{page_id}/revisions/{revision_number}` - Get revision
- `POST /api/wiki/{page_id}/link-task` - Link task to wiki page
- `POST /api/wiki/{page_id}/link-tasks` - Bulk link tasks
- `DELETE /api/wiki/{page_id}/link-task/{todo_id}` - Unlink task
- `GET /api/wiki/{page_id}/linked-tasks` - List linked tasks
- `GET /api/wiki/{page_id}/subscription` - Get subscription
- `POST /api/wiki/{page_id}/subscription` - Subscribe to page
- `DELETE /api/wiki/{page_id}/subscription` - Unsubscribe

### News Feed (`/api/news`)

- `GET /api/news` - List articles
- `GET /api/news/highlight` - Get highlighted/featured article
- `GET /api/news/stats` - Reading statistics
- `GET /api/news/{article_id}` - Get article
- `GET /api/news/sources` - List feed sources
- `POST /api/news/sources` - Add feed source
- `PUT /api/news/sources/{source_id}` - Update feed source
- `DELETE /api/news/sources/{source_id}` - Remove feed source
- `POST /api/news/sources/{source_id}/toggle` - Enable/disable source
- `POST /api/news/sources/{source_id}/fetch` - Force fetch source

### Snippets (`/api/snippets`)

- `GET /api/snippets` - List snippets
- `GET /api/snippets/categories` - List categories
- `POST /api/snippets` - Create snippet
- `GET /api/snippets/{snippet_id}` - Get snippet
- `PUT /api/snippets/{snippet_id}` - Update snippet
- `DELETE /api/snippets/{snippet_id}` - Delete snippet

### Notifications (`/api/notifications`)

- `GET /api/notifications` - List notifications
- `GET /api/notifications/unread-count` - Unread count
- `PUT /api/notifications/{notification_id}/read` - Mark read
- `PUT /api/notifications/read-all` - Mark all read
- `DELETE /api/notifications/{notification_id}` - Delete notification

### API Keys (`/api/api-keys`)

- `GET /api/api-keys` - List API keys
- `POST /api/api-keys` - Create API key
- `GET /api/api-keys/{key_id}` - Get API key
- `PUT /api/api-keys/{key_id}` - Update API key
- `DELETE /api/api-keys/{key_id}` - Delete API key
- `POST /api/api-keys/{key_id}/revoke` - Revoke API key

### Trash (`/api/trash`)

- `GET /api/trash` - List deleted tasks
- `POST /api/trash/{todo_id}/restore` - Restore deleted task

### Events (`/api/events`)

- `GET /api/events/stream` - Server-Sent Events stream for real-time updates

### Categories (`/api/categories`)

- `GET /api/categories` - List task categories/tags

### Registration Codes (`/api/registration-codes`)

- `GET /api/registration-codes` - List registration codes
- `POST /api/registration-codes` - Create registration code
- `DELETE /api/registration-codes/{code_id}` - Delete registration code
- `PATCH /api/registration-codes/{code_id}/deactivate` - Deactivate code

### Admin (`/api/admin`)

- `GET /api/admin/loki/summary` - Loki log summary
- `GET /api/admin/relay/channels` - List relay channels
- `GET /api/admin/relay/channels/{channel}/messages` - Get channel messages
- `POST /api/admin/relay/channels/{channel}/messages` - Post message
- `POST /api/admin/relay/channels/{channel}/clear` - Clear channel
- `GET /api/admin/service-accounts` - List service accounts
- `POST /api/admin/service-accounts` - Create service account
- `GET /api/admin/service-accounts/{account_id}` - Get service account
- `PATCH /api/admin/service-accounts/{account_id}` - Update service account
- `DELETE /api/admin/service-accounts/{account_id}` - Delete service account

## Task Model Fields

Tasks include agent integration fields for AI assistant workflows:

- `deadline_type` - Task urgency: `preferred`, `soft`, `hard`
- `time_horizon` - Planning horizon: `today`, `this_week`, `this_month`, `someday`
- `estimated_hours` / `actual_hours` - Time tracking
- `agent_actionable` - Whether an AI agent can complete without human
- `action_type` - Type: `research`, `review`, `code`, `email`, `data_entry`, etc.
- `autonomy_tier` - Risk level: 1=fully autonomous, 2=propose+execute, 3=propose+wait, 4=never
- `agent_status` - Agent processing state
- `agent_notes` - Agent-generated context
- `blocking_reason` - Why agent cannot proceed

## Architecture

```
app/
├── api/             # Route handlers (one file per resource)
│   └── oauth/       # OAuth 2.0 sub-routes
├── core/            # Security, errors, rate limiting, CSRF, sessions
├── db/              # Database engine and session factory
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response schemas
├── services/        # Business logic (news fetcher, summarizer, etc.)
├── dependencies.py  # FastAPI dependency injection (auth, db)
├── config.py        # Application settings
└── main.py          # FastAPI app and router registration
```

## Authentication

- **Session cookies** - Browser clients use `get_current_user` dependency
- **Bearer tokens** - OAuth 2.0 clients use `get_current_user_oauth` dependency
- **API keys** - Long-lived keys for programmatic access
- **Passkeys** - WebAuthn/FIDO2 passwordless authentication
- **GitHub OAuth** - Social login and account linking

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`
- `SECRET_KEY` - JWT signing key
- `BCRYPT_ROUNDS` - Password hashing cost (default: 12)
- `SESSION_DURATION_DAYS` - Session lifetime (default: 7)
- `FRONTEND_URL` - Frontend origin for CORS
- `ROOT_DOMAIN` - Domain for cookie scoping (production)
