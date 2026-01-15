# TaskManager Migration - Quick Start Guide

## 🎉 Migration Status: 90% Complete!

Both **Phase 1 (Backend)** and **Phase 2 (Frontend)** are fully implemented. You now have:

- ✅ Complete FastAPI backend (3,161 LOC, 40+ endpoints)
- ✅ Complete SvelteKit frontend (10 pages, 8 components)
- ✅ Docker Compose setup for side-by-side deployment
- ✅ All OAuth 2.0 flows implemented
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
cd backend

# Install dependencies
uv sync

# Run database migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
# Frontend runs on http://localhost:5173 by default
```

## 📁 Project Structure

```
taskmanager/
├── backend/                    # FastAPI backend (Phase 1 ✅)
│   ├── app/
│   │   ├── api/               # 13 API route files
│   │   ├── models/            # 7 SQLAlchemy models
│   │   ├── core/              # Security, errors, rate limiting
│   │   └── db/                # Database utilities
│   ├── tests/                 # 9 comprehensive test suites
│   ├── alembic/               # Database migrations
│   └── pyproject.toml         # uv dependencies
│
├── frontend/                  # SvelteKit frontend (Phase 2 ✅)
│   ├── src/
│   │   ├── routes/            # 10 pages (login, register, etc.)
│   │   ├── lib/
│   │   │   ├── components/   # 8 Svelte components
│   │   │   ├── stores/       # State management
│   │   │   └── api/          # API client
│   │   └── app.scss          # 1,221 lines of styles
│   └── package.json
│
├── services/                  # Legacy services
│   ├── web-app/              # Original Astro app (port 4321)
│   ├── mcp-auth/             # OAuth server (port 9000)
│   └── mcp-resource/         # MCP resource server (port 8001)
│
├── docker-compose.yml         # All services configuration
└── docs/
    └── MIGRATION_PLAN.md      # Detailed migration documentation
```

## 🔧 Common Commands

### Backend

```bash
cd backend

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
cd frontend

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
cd backend
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run with coverage
uv run pytest tests/ -v --cov=app
```

### Frontend Tests (E2E with Playwright)

```bash
cd frontend

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

## 🎯 Next Steps (Phase 3)

1. **Integration Testing**: Run E2E tests with Playwright
2. **Performance Validation**: Benchmark against legacy app
3. **Security Audit**: Review authentication, authorization, and input validation
4. **Deployment**: Deploy to production environment
5. **Cutover**: Switch from legacy Astro app to new SvelteKit app

## 📚 Documentation

- **Migration Plan**: `docs/MIGRATION_PLAN.md` - Comprehensive migration documentation
- **Backend README**: `backend/README.md` - Backend-specific documentation
- **Frontend README**: `frontend/README.md` - Frontend-specific documentation

## 🆘 Troubleshooting

### Backend won't start

1. Check database is running: `docker compose ps postgres`
2. Check environment variables in `.env`
3. Run migrations: `cd backend && uv run alembic upgrade head`

### Frontend can't connect to backend

1. Ensure backend is running on port 8000
2. Check CORS configuration in `backend/app/config.py`
3. Verify `VITE_API_URL` in frontend environment

### Database connection errors

1. Check PostgreSQL is running: `docker compose ps postgres`
2. Verify database credentials in `.env`
3. Check database URL format: `postgresql+asyncpg://user:pass@host:port/db`

## 🎊 Success!

The migration is **90% complete**! Both the backend and frontend are fully functional. The remaining 10% is integration testing, performance validation, and deployment.

You can now run both stacks side-by-side and compare functionality before cutover.
