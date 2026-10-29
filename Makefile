# Single entry point for development and CI (ADR 0001). Each target delegates to the
# project's own tooling: uv in backend/, pnpm in frontend/.

BACKEND := uv run --directory backend
FRONTEND := pnpm --dir frontend

# Local settings for `make dev`; see .env.example. Paths are resolved from the repository root.
ENV_FILE ?= .env
-include $(ENV_FILE)
# Export every variable the env file defines, so all ASSISTANT_* settings reach the API.
export $(shell sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' $(ENV_FILE) 2>/dev/null)
# Required, no default (GEN-20): `make dev-preflight` stops when it is missing.
ifdef ASSISTANT_DATA_DIR
export ASSISTANT_DATA_DIR := $(abspath $(ASSISTANT_DATA_DIR))
endif
# Where `make models` puts the models the API loads at runtime (ADR 0004).
export ASSISTANT_MODELS_DIR := $(abspath $(or $(ASSISTANT_MODELS_DIR),data/models))
export COREPACK_ENABLE_DOWNLOAD_PROMPT := 0
# Ports for `make dev`; override when another local service already uses one (API_PORT=8010 make dev).
export API_PORT ?= 8000
export UI_PORT ?= 5173

# Where `make api-client` writes the schema and generated types (ADR 0005).
API_OUT ?= $(CURDIR)/frontend/src/api

.PHONY: help setup models dev dev-preflight e2e test-integration check check-backend check-frontend check-api-client api-client test test-backend test-frontend node-version

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: node-version ## Install project dependencies
	uv sync --directory backend
	corepack enable pnpm
	$(FRONTEND) install --frozen-lockfile
	$(FRONTEND) exec playwright install chromium
	uvx pre-commit install

models: ## Download the parsing models into ASSISTANT_MODELS_DIR (the only step that needs the network)
	$(BACKEND) python scripts/download_models.py "$(ASSISTANT_MODELS_DIR)"

dev: node-version dev-preflight ## API on :8000 and UI on :5173 (API_PORT, UI_PORT), both with hot reload
	@mkdir -p "$(ASSISTANT_DATA_DIR)"
	@$(BACKEND) uvicorn assistant.app:main --factory --reload --port $(API_PORT) & api=$$!; \
	frontend/node_modules/.bin/vite frontend --port $(UI_PORT) & ui=$$!; \
	trap 'kill $$api $$ui 2>/dev/null' INT TERM EXIT; \
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

e2e: node-version ## Browser journeys: real API with the fake model, fresh data directory
	$(FRONTEND) e2e

test-backend: ## Backend tests
	$(BACKEND) pytest -q

test-integration: ## Tests with real adapters; needs `make models` and Tesseract
	HF_HUB_OFFLINE=1 $(BACKEND) pytest -q -m integration

test-frontend: ## Frontend tests
	$(FRONTEND) test

# Line continuations stay outside quotes: GNU Make passes them into quoted strings verbatim.
node-version:
	@want="$$(cat .nvmrc)"; have="$$(node -p 'process.versions.node.split(".")[0]')"; \
	if [ "$$have" != "$$want" ]; then \
	  echo "Node $$want required (found $$(node --version)). Run: nvm use"; exit 1; \
	fi

# Checks configuration and ports without starting anything (tested by scripts/ci/test-make.sh).
dev-preflight:
	@if [ -z "$(ASSISTANT_DATA_DIR)" ]; then \
	  echo "ASSISTANT_DATA_DIR is not set. Copy .env.example to .env, or export it."; exit 1; \
	fi
	@for port in $(API_PORT) $(UI_PORT); do \
	  if lsof -nP -iTCP:$$port -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "Port $$port is already in use. Stop that process or choose another port (API_PORT, UI_PORT)."; exit 1; \
	  fi; \
	done
