# TaskManager Backend

FastAPI backend for TaskManager application.

## Development

```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest tests/ -v

# Run linting
uv run ruff check .
uv run pyright
```

## Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```
