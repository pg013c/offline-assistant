# Single entry point for development and CI (ADR 0001). Each target delegates to the
# project's own tooling: uv in backend/, pnpm in frontend/.

BACKEND := uv run --directory backend
FRONTEND := pnpm --dir frontend

# Local settings for `make dev`; see .env.example. Paths are resolved from the repository root.
-include .env
ASSISTANT_DATA_DIR ?= data/storage
export ASSISTANT_DATA_DIR := $(abspath $(ASSISTANT_DATA_DIR))
export COREPACK_ENABLE_DOWNLOAD_PROMPT := 0
# Ports for `make dev`; override when another local service already uses one (API_PORT=8010 make dev).
export API_PORT ?= 8000
export UI_PORT ?= 5173

# Where `make api-client` writes the schema and generated types (ADR 0005).
API_OUT ?= $(CURDIR)/frontend/src/api

.PHONY: help setup dev check check-backend check-frontend check-api-client api-client test test-backend test-frontend node-version

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: node-version ## Install project dependencies
	uv sync --directory backend
	corepack enable pnpm
	$(FRONTEND) install --frozen-lockfile

dev: node-version ## API on :8000 and UI on :5173 (API_PORT, UI_PORT), both with hot reload
	@for port in $(API_PORT) $(UI_PORT); do \
	  if lsof -nP -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "Port $$port is already in use. Stop that process or choose another port (API_PORT, UI_PORT)."; exit 1; \
	  fi; \
	done
	@mkdir -p "$(ASSISTANT_DATA_DIR)"
	@trap 'kill 0' INT TERM EXIT; \
	$(BACKEND) uvicorn assistant.app:main --factory --reload --port $(API_PORT) & \
	$(FRONTEND) dev --port $(UI_PORT) & \
	wait

check: check-backend check-frontend check-api-client ## Format, lint, types, tests and API contract for everything

check-backend: ## Backend: ruff format, ruff lint, mypy, layer contracts, pytest
	$(BACKEND) ruff format --check .
	$(BACKEND) ruff check .
	$(BACKEND) mypy
	$(BACKEND) lint-imports --no-logo
	$(MAKE) test-backend

check-frontend: node-version ## Frontend: prettier, eslint, tsc, vitest
	$(FRONTEND) format:check
	$(FRONTEND) lint
	$(FRONTEND) typecheck
	$(MAKE) test-frontend

check-api-client: node-version ## API contract: the committed client matches the backend schema
	bash scripts/ci/check-api-client.sh

api-client: node-version ## Regenerate the TypeScript client from the backend's OpenAPI schema
	@mkdir -p "$(API_OUT)"
	$(BACKEND) python -m assistant.openapi > "$(API_OUT)/openapi.json"
	$(FRONTEND) exec openapi-typescript "$(API_OUT)/openapi.json" --output "$(API_OUT)/schema.d.ts" --silent

test: test-backend test-frontend ## Tests only

test-backend: ## Backend tests
	$(BACKEND) pytest -q

# --passWithNoTests only until the first frontend test lands (F-00 step 7).
test-frontend: ## Frontend tests
	$(FRONTEND) test --passWithNoTests

node-version:
	@node -e 'const want = require("fs").readFileSync(".nvmrc", "utf8").trim(); \
	  if (process.versions.node.split(".")[0] !== want) { \
	    console.error(`Node $${want} required (found $${process.version}). Run: nvm use`); process.exit(1) }'
