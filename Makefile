# Single entry point for development and CI (ADR 0001). Each target delegates to the
# project's own tooling: uv in backend/, pnpm in frontend/.

BACKEND := uv run --directory backend
FRONTEND := pnpm --dir frontend
EVALS := uv run --directory evals

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

# Qdrant for `make dev`, the integration tests and the journeys (ADR 0017), pinned by digest.
QDRANT_IMAGE := qdrant/qdrant:v1.20.0@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2
QDRANT_CONTAINER := offline-assistant-qdrant
export QDRANT_PORT ?= 6333

# The local LLM for `make llm` (ADR 0021): llama.cpp's llama-server on LLM_PORT.
export LLM_PORT ?= 8080
# The model file's path comes from its pin (pinned_models.py), so the two cannot drift apart.
LLM_FILE = $(shell $(BACKEND) python -c "from assistant.adapters.pinned_models import QWEN3_8B as m; print('$(ASSISTANT_MODELS_DIR)/' + m.directory + '/' + next(iter(m.files)))")

# The evaluation's judge for `make judge` (ADR 0022): llama-server on JUDGE_PORT.
export JUDGE_PORT ?= 8081
JUDGE_FILE = $(shell $(BACKEND) python -c "from assistant.adapters.pinned_models import QWEN3_30B_A3B as m; print('$(ASSISTANT_MODELS_DIR)/' + m.directory + '/' + next(iter(m.files)))")

# Evaluation corpus, fetched by `make eval-corpus` (ADR 0018).
export EVAL_CORPUS_DIR := $(abspath $(or $(EVAL_CORPUS_DIR),data/eval-corpus))

# Where `make api-client` writes the schema and generated types (ADR 0005).
API_OUT ?= $(CURDIR)/frontend/src/api

.PHONY: help setup models llm-models llm-preflight llm judge-models judge-preflight judge qdrant eval-corpus eval eval-answers check-evals dev dev-preflight e2e test-integration check check-backend check-frontend check-api-client api-client test test-backend test-frontend node-version

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

setup: node-version ## Install project dependencies
	uv sync --directory backend
	corepack enable pnpm
	$(FRONTEND) install --frozen-lockfile
	$(FRONTEND) exec playwright install chromium
	uv sync --directory evals
	pnpm --dir evals install --frozen-lockfile
	uvx pre-commit install

models: ## Download the parsing and embedding models into ASSISTANT_MODELS_DIR (the only step that needs the network)
	$(BACKEND) python scripts/download_models.py "$(ASSISTANT_MODELS_DIR)"

llm-models: ## Download the local LLM (Qwen3 8B, about 5 GB) into ASSISTANT_MODELS_DIR, checked by hash
	$(BACKEND) python scripts/download_models.py "$(ASSISTANT_MODELS_DIR)" --llm

llm-preflight: ## Check that make llm can start: llama-server installed, model file pinned, port free
	@$(BACKEND) python -c "from pathlib import Path; from assistant.adapters.pinned_models import LLM_MODELS, verify_models; verify_models(Path('$(ASSISTANT_MODELS_DIR)'), LLM_MODELS)" 2>/dev/null \
	  || { echo "The local LLM is missing or changed in $(ASSISTANT_MODELS_DIR). Fetch it with: make llm-models"; exit 1; }
	@command -v llama-server >/dev/null || { echo "llama-server is not installed. Install it with: brew install llama.cpp"; exit 1; }
	@if lsof -nP -iTCP:$(LLM_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  owner="$$(lsof -nP -iTCP:$(LLM_PORT) -sTCP:LISTEN | awk 'NR==2 {print $$1 " (pid " $$2 ")"}')"; \
	  echo "Port $(LLM_PORT) is already used by $$owner. Stop it or set LLM_PORT."; exit 1; \
	fi

llm: llm-preflight ## Serve the local LLM with llama-server on LLM_PORT (Metal, thinking off; ADR 0021)
	llama-server -m "$(LLM_FILE)" --alias qwen3-8b --host 127.0.0.1 --port $(LLM_PORT) \
	  --n-gpu-layers 99 --ctx-size 16384 --jinja --reasoning-budget 0

judge-models: ## Download the evaluation's judge (Qwen3 30B-A3B, about 18.6 GB) into ASSISTANT_MODELS_DIR, checked by hash
	$(BACKEND) python scripts/download_models.py "$(ASSISTANT_MODELS_DIR)" --judge

judge-preflight: ## Check that make judge can start: llama-server installed, judge file pinned, port free
	@$(BACKEND) python -c "from pathlib import Path; from assistant.adapters.pinned_models import JUDGE_MODELS, verify_models; verify_models(Path('$(ASSISTANT_MODELS_DIR)'), JUDGE_MODELS)" 2>/dev/null \
	  || { echo "The judge is missing or changed in $(ASSISTANT_MODELS_DIR). Fetch it with: make judge-models"; exit 1; }
	@command -v llama-server >/dev/null || { echo "llama-server is not installed. Install it with: brew install llama.cpp"; exit 1; }
	@if lsof -nP -iTCP:$(JUDGE_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  owner="$$(lsof -nP -iTCP:$(JUDGE_PORT) -sTCP:LISTEN | awk 'NR==2 {print $$1 " (pid " $$2 ")"}')"; \
	  echo "Port $(JUDGE_PORT) is already used by $$owner. Stop it or set JUDGE_PORT."; exit 1; \
	fi

judge: judge-preflight ## Serve the evaluation's judge with llama-server on JUDGE_PORT (thinking on; ADR 0023)
	llama-server -m "$(JUDGE_FILE)" --alias qwen3-30b-a3b --host 127.0.0.1 --port $(JUDGE_PORT) \
	  --n-gpu-layers 99 --ctx-size 16384 --jinja

eval-corpus: ## Download the evaluation corpus into EVAL_CORPUS_DIR, checked against pinned hashes
	$(EVALS) python -m harness.corpus "$(EVAL_CORPUS_DIR)"

eval: ## Retrieval evaluation on the corpus, compared with the baseline; needs models, qdrant, eval-corpus
	@curl -fs http://127.0.0.1:$(QDRANT_PORT)/readyz >/dev/null || { \
	  echo "Qdrant is not running on port $(QDRANT_PORT). Start it with: make qdrant"; exit 1; }
	HF_HUB_OFFLINE=1 $(EVALS) python -m harness.run

eval-answers: ## Answer evaluation against the local LLM, compared with its baseline; needs make llm, models, qdrant, eval-corpus
	@curl -fs http://127.0.0.1:$(LLM_PORT)/health >/dev/null || { \
	  echo "No model server on port $(LLM_PORT). Start it with: make llm"; exit 1; }
	@curl -fs http://127.0.0.1:$(QDRANT_PORT)/readyz >/dev/null || { \
	  echo "Qdrant is not running on port $(QDRANT_PORT). Start it with: make qdrant"; exit 1; }
	HF_HUB_OFFLINE=1 $(EVALS) python -m harness.run --answers

qdrant: ## Start Qdrant in Docker on QDRANT_PORT (data in ASSISTANT_DATA_DIR/qdrant, telemetry off)
	@if [ -z "$(ASSISTANT_DATA_DIR)" ]; then \
	  echo "ASSISTANT_DATA_DIR is not set. Copy .env.example to .env, or export it."; exit 1; \
	fi
	@if docker ps --format '{{.Names}}' | grep -qx $(QDRANT_CONTAINER); then \
	  echo "Qdrant is already running ($(QDRANT_CONTAINER))."; \
	elif docker ps -a --format '{{.Names}}' | grep -qx $(QDRANT_CONTAINER); then \
	  docker start $(QDRANT_CONTAINER) >/dev/null; \
	elif lsof -nP -iTCP:$(QDRANT_PORT) -sTCP:LISTEN >/dev/null 2>&1; then \
	  owner="$$(docker ps --filter publish=$(QDRANT_PORT) --format 'container {{.Names}}' | head -1)"; \
	  [ -n "$$owner" ] || owner="$$(lsof -nP -iTCP:$(QDRANT_PORT) -sTCP:LISTEN | awk 'NR==2 {print $$1 " (pid " $$2 ")"}')"; \
	  echo "Port $(QDRANT_PORT) is already used by $$owner. Stop it or set QDRANT_PORT."; exit 1; \
	else \
	  mkdir -p "$(ASSISTANT_DATA_DIR)/qdrant"; \
	  docker run -d --name $(QDRANT_CONTAINER) -p 127.0.0.1:$(QDRANT_PORT):6333 \
	    -e QDRANT__TELEMETRY_DISABLED=true -v "$(ASSISTANT_DATA_DIR)/qdrant:/qdrant/storage" \
	    $(QDRANT_IMAGE) >/dev/null; \
	fi
	@for attempt in $$(seq 30); do \
	  curl -fs http://127.0.0.1:$(QDRANT_PORT)/readyz >/dev/null && echo "Qdrant is ready on port $(QDRANT_PORT)." && exit 0; \
	  sleep 1; \
	done; \
	echo "Qdrant did not become ready; see: docker logs $(QDRANT_CONTAINER)"; exit 1

dev: node-version dev-preflight ## API on :8000 and UI on :5173 (API_PORT, UI_PORT), both with hot reload
	@mkdir -p "$(ASSISTANT_DATA_DIR)"
	@$(BACKEND) uvicorn assistant.app:main --factory --reload --port $(API_PORT) & api=$$!; \
	frontend/node_modules/.bin/vite frontend --port $(UI_PORT) & ui=$$!; \
	trap 'kill $$api $$ui 2>/dev/null' INT TERM EXIT; \
	wait

check: check-backend check-frontend check-api-client check-evals ## Format, lint, types, tests and API contract for everything

check-backend: ## Backend: ruff format, ruff lint, mypy, layer contracts, pytest
	$(BACKEND) ruff format --check .
	$(BACKEND) ruff check .
	$(BACKEND) mypy
	$(BACKEND) lint-imports --no-logo
	$(MAKE) test-backend

check-evals: ## Evaluation harness: ruff format, ruff lint, mypy, pytest
	$(EVALS) ruff format --check .
	$(EVALS) ruff check .
	$(EVALS) mypy
	$(EVALS) pytest -q

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

e2e: node-version ## Browser journeys on the full stack and the test model; needs `make models` and `make qdrant`
	@curl -fs http://127.0.0.1:$(QDRANT_PORT)/readyz >/dev/null || { \
	  echo "Qdrant is not running on port $(QDRANT_PORT). Start it with: make qdrant"; exit 1; }
	$(FRONTEND) e2e

test-backend: ## Backend tests
	$(BACKEND) pytest -q

test-integration: ## Tests with real adapters; needs `make models`, `make qdrant` and Tesseract
	HF_HUB_OFFLINE=1 $(BACKEND) pytest -q -m integration
	HF_HUB_OFFLINE=1 $(EVALS) pytest -q -m integration

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
