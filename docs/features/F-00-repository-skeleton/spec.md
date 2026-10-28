# F-00. Repository skeleton

- Status: approved
- Requirements: NFR-06, FR-50 (partly)
- Related ADRs: 0001, 0002, 0005, 0008, 0009, 0010

## Why

Every later feature needs the same foundation: a backend and a frontend project with their toolchains, one command that checks everything, CI that enforces it, and the guard rails from the ADRs (layer contract, generated API client, test-first commits) working before the first line of product code. Building this first means F-01 onwards starts with red/green commits from its first step.

## Scope

- **Backend** (`backend/`): uv project, Python 3.13, package `assistant` with the layer folders from [python.md](../../standards/python.md) (`domain`, `ports`, `services`, `adapters/fakes`, `api`), `app.py` composition root, `settings.py` (`pydantic-settings`, prefix `ASSISTANT_`), structlog setup. Tooling: ruff, mypy strict, pytest, import-linter with the layers contract from ADR 0002.
- **One endpoint:** `GET /api/health` returning status and version, so the whole chain (API, OpenAPI schema, generated client, UI, CI) has something real to carry.
- **Frontend** (`frontend/`): pnpm project, Vite, React 19, TypeScript strict, Tailwind, TanStack Query, ESLint, Prettier, Vitest with Testing Library. An app shell that shows the backend status through the generated client.
- **API contract:** `make api-client` exports the OpenAPI schema and generates the TypeScript client (`openapi-typescript` + `openapi-fetch`) into `frontend/src/api/`; CI fails if the committed client is out of date.
- **Makefile:** `setup`, `dev`, `check`, `test`, `api-client`.
- **Git hooks:** `pre-commit` running format, lint and type checks only, never tests (ADR 0009).
- **CI:** `Backend`, `Frontend` and `API contract` jobs added to `ci.yml` (ADR 0010).
- **Agent hook:** `format-on-edit` becomes active, since the formatters now exist.
- README "Getting started" for development.

## Out of scope

- Docker Compose, Qdrant, Langfuse, model servers: F-10 and later.
- `make eval` (F-04), `make offline-check` (F-10), `make models` (F-02/F-06).
- Playwright: set up in F-01 with the first user journey.
- Any product behaviour beyond the health endpoint.

## Acceptance criteria

- [ ] AC-1: Given a fresh clone with uv, pnpm and Node installed, when the developer runs `make setup` and then `make check`, then formatting, lint, type checks, tests and the API contract check run for both projects and pass.
- [ ] AC-2: When a client calls `GET /api/health`, then it receives `200` with `{"status": "ok", "version": "<package version>"}`, and the endpoint appears in the OpenAPI schema with a typed response.
- [ ] AC-3: Given a module in `services/` that imports from `adapters/`, when `make check` runs, then the import contract fails and names the forbidden import.
- [ ] AC-4: Given the API is running, when the UI loads, then the app shell shows "API: ok" and the version; given the API is unreachable, then it shows "API: unavailable" without crashing.
- [ ] AC-5: Given a change to an API schema without running `make api-client`, when CI runs, then the `API contract` job fails.
- [ ] AC-6: When `make dev` runs, then the API starts on port 8000 and the UI on port 5173 with `/api` proxied to the API, both with hot reload.
- [ ] AC-7: Given staged changes, when the developer commits, then the `pre-commit` hooks run formatting, lint and type checks and do not run the test suite.
- [ ] AC-8: Given a pull request, when CI runs, then `Backend`, `Frontend` and `API contract` jobs run alongside the existing jobs and pass.
- [ ] AC-9: Missing required settings fail at startup with a message naming the variable (GEN-20, GEN-50).

### Proof of each criterion

The mapping from criteria to the steps and tests that prove them is in [plan.md](plan.md#acceptance-criteria-mapping) (TEST-09). AC-1, AC-2, AC-3, AC-4, AC-8 and AC-9 have automated tests or CI jobs. AC-5, AC-6 and AC-7 were verified by hand, with the results noted in the plan, and are partly automated by `scripts/ci/test-make.sh`.

## Evaluation cases

Not applicable: no model behaviour.

## Decisions

1. **Python version:** 3.13. The model libraries (PyTorch, Docling, faster-whisper/CTranslate2) are reliably available for it; 3.14 gains nothing we need and risks missing wheels.
2. **Git hook runner:** `pre-commit` (Python tool, run through `uvx`), the most widely recognised option and one config for both projects. Alternative: lefthook.
3. **API path prefix:** all API routes under `/api` (`/api/health`), so the UI proxy and a future static server need one rule.
