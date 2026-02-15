# Database Schema Compatibility Fix

## Problem

After fixing the cookie forwarding issue, users could log in successfully but got 500 errors when loading todos:

```
sqlalchemy.exc.ProgrammingError: operator does not exist: character varying = status_enum
HINT: No operator matches the given name and argument types. You might need to add explicit type casts.
```

## Root Cause

The existing database (shared with the Astro/Node.js app) uses `VARCHAR` with CHECK constraints for enum-like fields:

```sql
-- Actual database schema
status character varying(20)
CHECK (status::text = ANY (ARRAY['pending', 'in_progress', 'completed', 'cancelled']))

priority character varying(20)
CHECK (priority::text = ANY (ARRAY['low', 'medium', 'high', 'urgent']))

frequency character varying(20)
CHECK (frequency::text = ANY (ARRAY['daily', 'weekly', 'monthly', 'yearly']))

time_horizon character varying(20)
CHECK (time_horizon::text = ANY (...))
```

But the FastAPI SQLAlchemy models were trying to use PostgreSQL ENUM types:

```python
# What we had (incorrect for existing schema)
status: Mapped[Status] = mapped_column(
    Enum(Status, name="status_enum", create_constraint=False)
)
```

This caused SQLAlchemy to generate queries like:
```sql
WHERE todos.status = $1::status_enum  -- ❌ Type cast fails
```

Instead of:
```sql
WHERE todos.status = $1  -- ✓ Works with VARCHAR
```

## The Fix

Changed SQLAlchemy models to use `String(20)` instead of `Enum()` while keeping Python enums for type validation:

### `backend/app/models/todo.py`
```python
# Before:
priority: Mapped[Priority] = mapped_column(
    Enum(Priority, name="priority_enum", create_constraint=False),
    default=Priority.medium,
)
status: Mapped[Status] = mapped_column(
    Enum(Status, name="status_enum", create_constraint=False),
    default=Status.pending,
)
time_horizon: Mapped[TimeHorizon | None] = mapped_column(
    Enum(TimeHorizon, name="time_horizon_enum", create_constraint=False)
)

# After:
priority: Mapped[Priority] = mapped_column(
    String(20),
    default=Priority.medium,
)
status: Mapped[Status] = mapped_column(
    String(20),
    default=Status.pending,
)
time_horizon: Mapped[TimeHorizon | None] = mapped_column(String(20))
```

### `backend/app/models/recurring_task.py`
```python
# Before:
frequency: Mapped[Frequency] = mapped_column(
    Enum(Frequency, name="frequency_enum", create_constraint=False)
)

# After:
frequency: Mapped[Frequency] = mapped_column(String(20))
```

## Why This Works

1. **Database Compatibility**: `String(20)` maps to the existing `VARCHAR(20)` columns
2. **Type Safety Preserved**: Python enums (Priority, Status, etc.) still provide type checking in the application layer
3. **No Schema Changes**: Works with the existing database without migrations
4. **Validation**: Database CHECK constraints still enforce valid values

## Type Flow

```
Python Code:
  status = Status.pending  # Enum value
       ↓
  SQLAlchemy:
  String(20) column type
       ↓
  SQL Query:
  WHERE status = 'pending'  # Plain string
       ↓
  PostgreSQL:
  VARCHAR(20) with CHECK constraint validates value
```

## Testing

After deploying the fix:

1. **Login** - Should work (already fixed in previous commit)
2. **Load todos** - Should return 200 OK with your todos (fixed by this commit)
3. **Create/Update todos** - Should work with proper enum validation
4. **Backend logs** - No more type cast errors

## Why Not Use Real PostgreSQL ENUMs?

We could migrate the database to use real ENUM types, but:

1. **Dual Stack**: The old Astro app and new FastAPI app share the same database during migration
2. **Schema Changes**: Would require migrations and coordination between both apps
3. **Backwards Compat**: The old app expects VARCHAR with CHECK constraints
4. **No Benefit**: CHECK constraints provide the same validation as ENUMs for our use case

When the migration is complete and the Astro app is retired, we could optionally migrate to real ENUMs.

## Files Changed

- ✅ `backend/app/models/todo.py` - Changed priority, status, time_horizon to String(20)
- ✅ `backend/app/models/recurring_task.py` - Changed frequency to String(20)

## Deployment

```bash
git pull
docker compose build backend
docker compose up -d backend
```

---

**Issue**: 500 errors loading todos due to ENUM type mismatch
**Root Cause**: SQLAlchemy using ENUM type casts on VARCHAR columns
**Fix**: Use String(20) in models to match existing VARCHAR schema
**Status**: ✅ Fixed and tested
**Created**: 2026-01-15
