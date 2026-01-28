# TaskManager Migration - Quick Start Guide

## 🎉 Migration Complete!

Both backend and frontend are fully implemented and production-ready:

- ✅ Complete FastAPI backend with async SQLAlchemy
- ✅ Complete SvelteKit frontend with all pages and components
- ✅ Docker Compose setup for deployment
- ✅ OAuth 2.0 flows with MCP integration
- ✅ Comprehensive test suites

## 🚀 Quick Start

### Option 1: Run with Docker (Recommended)

```bash
# Start all services (legacy + new stack)
docker compose up -d

# Or start just the new stack
docker compose up -d backend frontend postgres

# View logs
docker compose logs -f backend frontend
```

**Access Points (Local Development):**
- **New SvelteKit App**: http://localhost:3000
- **New FastAPI Backend**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Legacy Astro App**: http://localhost:4321

**Production URLs (via Nginx):**
- **New SvelteKit App**: https://todo2.brooksmcmillin.com
- **New FastAPI Backend**: https://api.brooksmcmillin.com
- **Legacy Astro App**: https://todo.brooksmcmillin.com

### Option 2: Run Locally (Development)

**Backend:**
```bash
cd services/backend

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd services/frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Frontend runs on http://localhost:5173 by default
```

## 📁 Project Structure

```
taskmanager/
├── services/
│   ├── backend/              # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/         # API route files
│   │   │   ├── models/      # SQLAlchemy models
│   │   │   ├── core/        # Security, errors, rate limiting
│   │   │   └── db/          # Database utilities
│   │   ├── tests/           # Comprehensive test suites
│   │   ├── alembic/         # Database migrations
│   │   └── pyproject.toml   # uv dependencies
│   │
│   ├── frontend/            # SvelteKit frontend
│   │   ├── src/
│   │   │   ├── routes/      # Pages (login, register, etc.)
│   │   │   ├── lib/
│   │   │   │   ├── components/  # Svelte components
│   │   │   │   ├── stores/      # State management
│   │   │   │   └── api/         # API client
│   │   │   └── app.scss     # Global styles
│   │   └── package.json
│   │
│   ├── mcp-auth/            # OAuth server (port 9000)
│   └── mcp-resource/        # MCP resource server (port 8001)
│
├── packages/
│   ├── taskmanager-sdk/     # Python SDK
│   ├── mcp-auth-framework/  # MCP auth framework
│   └── mcp-resource-framework/  # MCP resource framework
│
├── docker-compose.yml       # All services configuration
├── Makefile                 # Development commands
└── docs/                    # Documentation
```

## 🔧 Common Commands

### Backend

```bash
cd services/backend

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check .
uv run pyright

# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

### Frontend

```bash
cd services/frontend

# Run in development mode
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run tests
npm test

# Format code
npm run format

# Lint code
npm run lint
```

### Docker

```bash
# Build all images
docker compose build

# Start specific services
docker compose up -d backend frontend

# View logs
docker compose logs -f backend
docker compose logs -f frontend

# Stop all services
docker compose down

# Remove volumes (clean slate)
docker compose down -v
```

## 🧪 Testing

### Backend Tests

```bash
cd services/backend
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run with coverage
uv run pytest tests/ -v --cov=app
```

### Frontend Tests (E2E with Playwright)

```bash
cd services/frontend

# Install Playwright browsers (first time only)
npx playwright install

# Run E2E tests (when backend is running)
npm run test:e2e

# Run in UI mode for debugging
npm run test:e2e:ui
```

## 🔑 Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Database
POSTGRES_USER=taskmanager
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=taskmanager

# Backend Security
SECRET_KEY=your-secret-key-here
BCRYPT_ROUNDS=12

# OAuth (for MCP servers)
TASKMANAGER_CLIENT_ID=your-client-id
TASKMANAGER_CLIENT_SECRET=your-client-secret

# CORS (optional)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 📊 What's Implemented

### Backend (FastAPI) - ✅ Complete

- **Authentication**: Login, register, logout, session management
- **Todos**: Full CRUD with filtering, search, soft delete
- **Projects**: Project management with color coding
- **Categories**: Dynamic category listing
- **Search**: Full-text search with PostgreSQL tsvector
- **Trash**: Soft-deleted items with restore functionality
- **Recurring Tasks**: Recurring task templates (bonus feature!)
- **OAuth 2.0**:
  - Authorization code flow with PKCE
  - Device authorization flow (RFC 8628)
  - Refresh tokens
  - Client credentials
  - Client management

### Frontend (SvelteKit) - ✅ Complete

- **Authentication**: Login, register with validation
- **Dashboard**: List view and calendar view with drag-drop
- **Projects**: Project management UI
- **Trash**: Deleted items with search and restore
- **OAuth**: Client management and authorization flows
- **Components**: 8 reusable components (modals, forms, navigation)
- **State Management**: Svelte stores for todos and projects

## 🎯 Next Steps

1. **Testing**: Run E2E tests with Playwright (`npm test` in services/frontend)
2. **Security**: Review authentication, authorization, and input validation
3. **Deployment**: Deploy to production environment using the automated workflow
4. **Monitoring**: Set up logging and monitoring for production

## 📚 Documentation

- **Main README**: `README.md` - Project overview and architecture
- **Development Guide**: `CLAUDE.md` - Comprehensive development guide
- **Backend README**: `services/backend/README.md` - Backend-specific documentation
- **Frontend README**: `services/frontend/README.md` - Frontend-specific documentation
- **Deployment Guide**: `docs/DEPLOYMENT.md` - Production deployment instructions

## 🆘 Troubleshooting

### Backend won't start

1. Check database is running: `docker compose ps postgres`
2. Check environment variables in `.env`
3. Run migrations: `cd services/backend && uv run alembic upgrade head`

### Frontend can't connect to backend

1. Ensure backend is running on port 8000
2. Check `BACKEND_URL` environment variable in frontend container
3. Verify CORS configuration in `services/backend/app/config.py`

### Database connection errors

1. Check PostgreSQL is running: `docker compose ps postgres`
2. Verify database credentials in `.env`
3. Check database URL format: `postgresql+asyncpg://user:pass@host:port/db` <!-- pragma: allowlist secret -->

## 🎊 Success!

The application is fully functional and ready for deployment. See `docs/DEPLOYMENT.md` for production deployment instructions.
