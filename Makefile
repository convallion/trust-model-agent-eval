.PHONY: help install dev server sdk test lint format clean docker-up docker-down docker-build migrate

# ═══════════════════════════════════════════════════════════════════════════════
# TrustModel Agent Eval - Development Commands
# ═══════════════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo "TrustModel Agent Eval - Available Commands"
	@echo "==========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ═══════════════════════════════════════════════════════════════════════════════
# Installation
# ═══════════════════════════════════════════════════════════════════════════════

install: install-server install-sdk ## Install all dependencies

install-server: ## Install server dependencies
	cd server && pip install -e ".[dev]"

install-sdk: ## Install SDK dependencies
	cd sdk && pip install -e ".[dev]"

dev: ## Install all in development mode
	pip install -e "./server[dev]" -e "./sdk[dev]"

# ═══════════════════════════════════════════════════════════════════════════════
# Development Servers
# ═══════════════════════════════════════════════════════════════════════════════

server: ## Run the API server locally (requires DB)
	cd server && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker locally
	cd server && celery -A app.workers.celery_app worker --loglevel=info

beat: ## Run Celery beat scheduler locally
	cd server && celery -A app.workers.celery_app beat --loglevel=info

# ═══════════════════════════════════════════════════════════════════════════════
# Docker
# ═══════════════════════════════════════════════════════════════════════════════

docker-build: ## Build all Docker images
	docker-compose build

docker-up: ## Start all services
	docker-compose up -d

docker-up-logs: ## Start all services with logs
	docker-compose up

docker-down: ## Stop all services
	docker-compose down

docker-clean: ## Stop and remove all containers, volumes
	docker-compose down -v --remove-orphans

docker-logs: ## View logs from all services
	docker-compose logs -f

docker-logs-api: ## View API server logs
	docker-compose logs -f api

docker-shell: ## Open shell in API container
	docker-compose exec api /bin/bash

docker-db: ## Open psql shell in database container
	docker-compose exec db psql -U trustmodel -d trustmodel

# ═══════════════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════════════

migrate: ## Run database migrations
	cd server && alembic upgrade head

migrate-create: ## Create new migration (usage: make migrate-create msg="description")
	cd server && alembic revision --autogenerate -m "$(msg)"

migrate-downgrade: ## Rollback last migration
	cd server && alembic downgrade -1

migrate-history: ## Show migration history
	cd server && alembic history

# ═══════════════════════════════════════════════════════════════════════════════
# Testing
# ═══════════════════════════════════════════════════════════════════════════════

test: test-server test-sdk ## Run all tests

test-server: ## Run server tests
	cd server && pytest tests/ -v --cov=app --cov-report=term-missing

test-sdk: ## Run SDK tests
	cd sdk && pytest tests/ -v --cov=trustmodel --cov-report=term-missing

test-integration: ## Run integration tests
	pytest tests/integration/ -v

test-fast: ## Run tests without coverage
	pytest tests/ -v -x

# ═══════════════════════════════════════════════════════════════════════════════
# Code Quality
# ═══════════════════════════════════════════════════════════════════════════════

lint: ## Run linting on all code
	ruff check server/app sdk/src tests
	mypy server/app sdk/src

format: ## Format all code
	ruff format server/app sdk/src tests
	ruff check --fix server/app sdk/src tests

check: lint test ## Run all checks (lint + test)

# ═══════════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════════

clean: ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

init-ca: ## Initialize the Certificate Authority keys
	cd server && python -c "from app.ca.authority import CertificateAuthority; CertificateAuthority.initialize()"

generate-secret: ## Generate a new secret key
	python -c "import secrets; print(secrets.token_urlsafe(32))"

# ═══════════════════════════════════════════════════════════════════════════════
# Documentation
# ═══════════════════════════════════════════════════════════════════════════════

docs: ## Build documentation
	cd docs && mkdocs build

docs-serve: ## Serve documentation locally
	cd docs && mkdocs serve

# ═══════════════════════════════════════════════════════════════════════════════
# Release
# ═══════════════════════════════════════════════════════════════════════════════

build-sdk: ## Build SDK package
	cd sdk && python -m build

publish-sdk: ## Publish SDK to PyPI (requires credentials)
	cd sdk && python -m twine upload dist/*
