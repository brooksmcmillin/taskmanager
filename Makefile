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
	cd services/web-app && npm install
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

test:  ## Run all tests
	cd services/web-app && npm test -- --run
	cd services/mcp-auth && uv run pytest tests/ -v
	cd services/mcp-resource && uv run pytest tests/ -v
	cd packages/taskmanager-sdk && uv run pytest tests/ -v

test-web:  ## Run web-app tests
	cd services/web-app && npm test

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
	@echo "Linting web-app..."
	cd services/web-app && npm run lint
	@echo "Linting Python services..."
	cd services/mcp-auth && uv run ruff check .
	cd services/mcp-resource && uv run ruff check .
	cd packages/taskmanager-sdk && uv run ruff check .

format:  ## Auto-format code
	cd services/web-app && npm run format
	cd services/mcp-auth && uv run ruff format . && uv run ruff check --fix .
	cd services/mcp-resource && uv run ruff format . && uv run ruff check --fix .
	cd packages/taskmanager-sdk && uv run ruff format . && uv run ruff check --fix .

typecheck:  ## Run type checking
	cd services/mcp-auth && uv run pyright
	cd services/mcp-resource && uv run pyright
	cd packages/taskmanager-sdk && uv run pyright

# =============================================================================
# Security
# =============================================================================

security:  ## Run security checks
	@echo "Running npm audit..."
	cd services/web-app && npm audit || true
	@echo "Running pip-audit on Python services..."
	cd services/mcp-auth && uv run pip-audit || true
	cd services/mcp-resource && uv run pip-audit || true
	cd packages/taskmanager-sdk && uv run pip-audit || true
	@echo "Running bandit..."
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

migrate:  ## Run database migrations
	cd services/web-app && npm run migrate:up

migrate-create:  ## Create a new migration (usage: make migrate-create name=migration_name)
	cd services/web-app && npm run migrate:create $(name)

migrate-rollback:  ## Rollback last migration (usage: make migrate-rollback version=VERSION)
	cd services/web-app && npm run migrate:rollback $(version)

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
