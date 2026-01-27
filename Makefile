.PHONY: help install test lint format security clean docker-build docker-up docker-down pre-commit

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# =============================================================================
# Installation
# =============================================================================

install:  ## Install all dependencies
	cd services/frontend && npm install
	cd services/backend && uv sync
	cd services/mcp-auth && uv sync
	cd services/mcp-resource && uv sync
	cd packages/taskmanager-sdk && uv sync

install-dev:  ## Install development dependencies including pre-commit
	$(MAKE) install
	pip install pre-commit
	pre-commit install

# =============================================================================
# Testing
# =============================================================================

test-db-setup:  ## Set up test database (start postgres and create test DB)
	@echo "Checking for Docker volume..."
	@docker volume inspect db_postgres_data > /dev/null 2>&1 || (echo "Creating db_postgres_data volume..." && docker volume create db_postgres_data)
	@echo "Starting PostgreSQL..."
	@docker compose up -d postgres
	@echo "Waiting for PostgreSQL to be ready..."
	@sleep 3
	@docker exec postgres_db psql -U taskmanager -d taskmanager -c "SELECT 1;" > /dev/null 2>&1 || (echo "Waiting longer for postgres..." && sleep 3)
	@echo "Creating test database..."
	@docker exec postgres_db psql -U taskmanager -d taskmanager -c "CREATE DATABASE taskmanager_test;" 2>/dev/null || echo "Test database already exists (this is fine)"
	@echo "Test database ready!"

test:  ## Run all tests
	cd services/frontend && npm test
	cd services/backend && uv run pytest tests/ -v
	cd services/mcp-auth && uv run pytest tests/ -v
	cd services/mcp-resource && uv run pytest tests/ -v
	cd packages/taskmanager-sdk && uv run pytest tests/ -v

test-local:  ## Run all tests with local database setup
	$(MAKE) test-db-setup
	$(MAKE) test-frontend
	$(MAKE) test-backend
	$(MAKE) test-mcp-auth
	$(MAKE) test-mcp-resource
	$(MAKE) test-sdk

test-frontend:  ## Run frontend tests (SvelteKit)
	cd services/frontend && npm test

test-backend:  ## Run backend tests (FastAPI)
	cd services/backend && uv run pytest tests/ -v

test-backend-local:  ## Run backend tests with local database setup
	$(MAKE) test-db-setup
	cd services/backend && uv run pytest tests/ -v

test-mcp-auth:  ## Run mcp-auth tests
	cd services/mcp-auth && uv run pytest tests/ -v

test-mcp-resource:  ## Run mcp-resource tests
	cd services/mcp-resource && uv run pytest tests/ -v

test-sdk:  ## Run SDK tests
	cd packages/taskmanager-sdk && uv run pytest tests/ -v

test-cov:  ## Run tests with coverage
	cd packages/taskmanager-sdk && uv run pytest tests/ -v --cov=taskmanager_sdk --cov-report=html

# =============================================================================
# Linting & Formatting
# =============================================================================

lint:  ## Run all linting checks
	@echo "Linting frontend..."
	cd services/frontend && npm run lint
	@echo "Linting Python services..."
	cd services/backend && uv run ruff check .
	cd services/mcp-auth && uv run ruff check .
	cd services/mcp-resource && uv run ruff check .
	cd packages/taskmanager-sdk && uv run ruff check .

format:  ## Auto-format code
	cd services/frontend && npm run format
	cd services/backend && uv run ruff format . && uv run ruff check --fix .
	cd services/mcp-auth && uv run ruff format . && uv run ruff check --fix .
	cd services/mcp-resource && uv run ruff format . && uv run ruff check --fix .
	cd packages/taskmanager-sdk && uv run ruff format . && uv run ruff check --fix .

typecheck:  ## Run type checking
	cd services/backend && uv run pyright
	cd services/mcp-auth && uv run pyright
	cd services/mcp-resource && uv run pyright
	cd packages/taskmanager-sdk && uv run pyright

# =============================================================================
# Security
# =============================================================================

security:  ## Run security checks
	@echo "Running npm audit..."
	cd services/frontend && npm audit || true
	@echo "Running pip-audit on Python services..."
	cd services/backend && uv run pip-audit || true
	cd services/mcp-auth && uv run pip-audit || true
	cd services/mcp-resource && uv run pip-audit || true
	cd packages/taskmanager-sdk && uv run pip-audit || true
	@echo "Running bandit..."
	cd services/backend && uv run bandit -r app/ || true
	cd services/mcp-auth && uv run bandit -r mcp_auth/ || true
	cd services/mcp-resource && uv run bandit -r mcp_resource/ || true

# =============================================================================
# Pre-commit
# =============================================================================

pre-commit:  ## Run pre-commit hooks on all files
	pre-commit run --all-files

# =============================================================================
# Docker
# =============================================================================

docker-build:  ## Build Docker images
	docker compose build

docker-up:  ## Start Docker containers
	docker compose up -d

docker-down:  ## Stop Docker containers
	docker compose down

docker-logs:  ## Show Docker logs
	docker compose logs -f

docker-restart:  ## Restart Docker containers
	docker compose restart

# =============================================================================
# Database
# =============================================================================

migrate:  ## Run database migrations (Alembic)
	cd services/backend && uv run alembic upgrade head

migrate-create:  ## Create a new migration (usage: make migrate-create msg="message")
	cd services/backend && uv run alembic revision --autogenerate -m "$(msg)"

migrate-rollback:  ## Rollback one migration
	cd services/backend && uv run alembic downgrade -1

backup-db:  ## Backup production database
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	echo "📦 Creating database backup: backups/db_backup_$$TIMESTAMP.sql"; \
	docker exec postgres_db pg_dump -U taskmanager -d taskmanager > backups/db_backup_$$TIMESTAMP.sql && \
	echo "✅ Backup created successfully" || echo "❌ Backup failed"

restore-db:  ## Restore database from latest backup (usage: make restore-db or make restore-db file=backups/db_backup_20240126_120000.sql)
	@if [ -z "$(file)" ]; then \
		LATEST=$$(ls -t backups/db_backup_*.sql 2>/dev/null | head -1); \
		if [ -z "$$LATEST" ]; then \
			echo "❌ No backup files found in backups/"; \
			exit 1; \
		fi; \
		echo "📥 Restoring from latest backup: $$LATEST"; \
		docker exec -i postgres_db psql -U taskmanager -d taskmanager < "$$LATEST"; \
	else \
		echo "📥 Restoring from: $(file)"; \
		docker exec -i postgres_db psql -U taskmanager -d taskmanager < "$(file)"; \
	fi && echo "✅ Database restored successfully" || echo "❌ Restore failed"

list-backups:  ## List available database backups
	@echo "Available database backups:"
	@ls -lh backups/db_backup_*.sql 2>/dev/null || echo "No backups found"

# =============================================================================
# Cleanup
# =============================================================================

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/

# =============================================================================
# All-in-one
# =============================================================================

all: clean install lint test security  ## Run all checks
