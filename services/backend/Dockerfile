# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app

# Copy installed dependencies
COPY --from=builder /app/.venv /app/.venv

# Copy application
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Set environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Create non-root user and uploads directory
RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /app/uploads && \
    chown appuser:appuser /app/uploads
USER appuser

EXPOSE 8000

# Run with uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
