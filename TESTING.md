# Testing the Project Filter Feature

This guide helps you quickly set up test data to test the new project filter functionality.

## Quick Start

### 1. Start the Backend Services

```bash
# Start PostgreSQL and backend API
docker compose up -d postgres backend
```

Wait a few seconds for the backend to be ready.

### 2. Seed Test Data

The easiest way is to use the Makefile target:

```bash
make seed-data
```

Or run the script directly:

```bash
cd services/backend
uv run python scripts/seed_test_data.py
```

This will:
- ✅ Check that you're using a development database (not production)
- 🧹 Clean up any existing test data
- 👤 Create a test user: email `testuser@example.com` / password `TestPass123!`
- 📁 Create 5 projects (Work, Personal, Learning, Health, Home)
- 📝 Create 50 tasks (10 per project) with realistic data:
  - 90% have due dates (0-14 days from now)
  - 10% have no due date
  - Random priorities
  - Random estimated hours
  - Some have tags

### 3. Start the Frontend (if not already running)

The frontend should already be running at http://10.0.13.55:3000/ or http://localhost:3000/

If not:
```bash
cd services/frontend
npm run dev
```

### 4. Test the Filter

1. Open http://localhost:3000/ in your browser
2. Login with:
   - **Email**: `testuser@example.com`
   - **Password**: `TestPass123!`
3. You'll see the new **Filter by Project** dropdown between the view toggle and the task list
4. Test filtering:
   - Select "Work" → See only work tasks
   - Select "Personal" → See only personal tasks
   - Select "All Projects" → See all tasks
5. Test that filter persists:
   - Select a project
   - Switch between List and Calendar views → Filter stays applied
   - Complete a task → Filter stays applied
   - Refresh the page → Filter stays applied (in URL)
   - Share the URL with `?project_id=1` → Filter is preserved

## Alternative: Custom Test Data

### Different email
```bash
cd services/backend
uv run python scripts/seed_test_data.py --user-email mytest@example.com
```

### More tasks per project
```bash
cd services/backend
uv run python scripts/seed_test_data.py --tasks-per-project 20
```

### Skip confirmation (for automation)
```bash
make seed-data-quick
# or
cd services/backend
uv run python scripts/seed_test_data.py --skip-confirm
```

## Database Safety

The seed script includes safety checks:

✅ **Safe databases** (script will run):
- `taskmanager` (default)
- `taskmanager_dev`
- `taskmanager_test`
- Any database with "dev", "test", "development", or "local" in the name

❌ **Unsafe databases** (script will refuse):
- Any database with "prod", "production", "live", or "main" in the name

⚠️ **Unclear databases** (script will warn and ask for confirmation):
- Any other database name

## Cleanup

The script automatically cleans up existing test data before seeding new data, so you can run it multiple times safely.

To manually clean up:
```bash
# Just delete the test user via the app UI or database
# (all tasks and projects will cascade delete)
```

## Troubleshooting

### "Database connection failed"
Make sure PostgreSQL is running:
```bash
docker compose up -d postgres
```

### "No module named 'app'"
Make sure you're running from the backend directory:
```bash
cd services/backend
uv run python scripts/seed_test_data.py
```

### Backend not responding
Start the backend:
```bash
docker compose up -d backend
# or run locally
cd services/backend
uv run uvicorn app.main:app --reload
```

### Need to reset everything
```bash
# Stop all services
docker compose down

# Remove database volume (WARNING: deletes ALL data)
docker volume rm taskmanager_db_postgres_data

# Start fresh
docker compose up -d postgres backend
make migrate
make seed-data
```

## What's New

The project filter feature adds:

1. **`ProjectFilter.svelte` component**: Reusable dropdown filter
2. **URL-based filter state**: Filter selection stored in `?project_id=X`
3. **Filter applies to both views**: List and Calendar views both respect the filter
4. **Filter persists**: Across page refreshes, task operations, and view switches

Test all of these behaviors to ensure everything works correctly!
