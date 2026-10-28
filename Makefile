# Single entry point for development and CI (ADR 0001). Each target delegates to the
# project's own tooling: uv in backend/, pnpm in frontend/.

BACKEND := uv run --directory backend

.PHONY: help setup check check-backend test test-backend

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: ## Install project dependencies
	uv sync --directory backend

check: check-backend ## Format, lint, types and tests for everything

check-backend: ## Backend: ruff format, ruff lint, mypy, layer contracts, pytest
	$(BACKEND) ruff format --check .
	$(BACKEND) ruff check .
	$(BACKEND) mypy
	$(BACKEND) lint-imports --no-logo
	$(MAKE) test-backend

test: test-backend ## Tests only

test-backend: ## Backend tests
	$(BACKEND) pytest -q
