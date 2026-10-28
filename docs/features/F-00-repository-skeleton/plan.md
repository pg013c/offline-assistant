# F-00. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- The repository holds documentation, agent tooling (`.claude/`), CI (`docs`, `tooling`, `commits` jobs) and shell scripts. There is no application code; `backend/` and `frontend/` contain only `CLAUDE.md`.
- `scripts/lib/test-paths.sh` already defines test paths (`backend/tests/*`, `*.test.tsx`, ...). New tests must live under those paths so the `tdd-guard` hook and the commit check apply to them.
- `.claude/hooks/format-on-edit.sh` runs ruff and Prettier once `backend/pyproject.toml` and `frontend/node_modules` exist; no change needed.
- `main` is protected: pull request required, checks `Docs`, `Tooling`, `Commit rules` required and up to date, rules apply to admins, merge commits only. The new CI jobs must be added to the required checks after this feature merges.
- Local toolchain: uv 0.12, pnpm 11, Node 22 (Node 24 to install via nvm), Docker installed. Python 3.13 is installed by uv.

## Design

- **Dependencies:** [ADR 0011](../../adr/0011-baseline-dependencies.md), accepted with this plan.
- **Commits without behaviour:** steps of kind `setup` are one `build(...)`/`ci(...)` commit, as now described in [workflow.md §4](../../workflow.md#4-the-redgreen-loop).
- **Backend entry points:** `assistant.app:create_app(settings: Settings) -> FastAPI` builds the app; `assistant.app:main` is the application factory for uvicorn (`--factory`), which loads settings from the environment; importing the module never reads the environment, so tests can build apps with their own settings.
- **Settings:** `Settings` with prefix `ASSISTANT_`; the one required field in F-00 is `data_dir: Path` (storage root, needed from F-01 and by GEN-42). `.env.example` documents it; `make dev` loads `.env`.
- **Health:** `GET /api/health` → `HealthResponse(status: Literal["ok"], version: str)`, version from package metadata. Route in `api/routes/health.py`, response model in `api/schemas.py`. No service: there is no domain behaviour yet.
- **Schema export:** `python -m assistant.openapi` prints the OpenAPI JSON. It sits next to `app.py`, not in `api/`, because it builds the whole app and `api` may not import `app` (layer contract). Operation ids are the route function names (`get_health`). `make api-client` writes it to `frontend/src/api/openapi.json` and runs `openapi-typescript` to `frontend/src/api/schema.d.ts`. The contract check (`scripts/ci/check-api-client.sh`, part of `make check` and the `API contract` CI job) regenerates into a temporary directory and fails if the result differs from `frontend/src/api`, so it works on uncommitted changes too.
- **Frontend:** `src/api/client.ts` creates the `openapi-fetch` client with base URL `/`. `src/features/status/useApiHealth.ts` (TanStack Query) and `src/features/status/ApiStatus.tsx` render "API: ok · v0.1.0" or "API: unavailable". `App.tsx` is the shell with a header holding `ApiStatus`. UI tests mock HTTP with msw.
- **Makefile:** `setup` (uv sync, pnpm install, pre-commit install), `dev` (uvicorn with reload on :8000 and Vite on :5173, proxy `/api` → :8000), `check`, `test`, `api-client`, plus `check-backend` and `check-frontend` used by CI. Ports are configurable with `API_PORT` and `UI_PORT`, and `make dev` stops early if a port is taken.

## Steps

### Step 1. Scaffold the backend project

- Kind: setup
- Change: `backend/pyproject.toml` (Python 3.13, dependencies from ADR 0011, ruff rules from PY-02, mypy strict, pytest with `integration` marker), `uv.lock`, `src/assistant/` with empty `domain`, `ports`, `services`, `adapters/fakes`, `api` packages, `.python-version`; root `Makefile` with `check-backend` (ruff format --check, ruff check, mypy, pytest) and `check`.
- Done when: `make check` runs and passes (pytest with no tests allowed for this step only).
- Commit: `build(backend): scaffold uv project with ruff, mypy and pytest`
- [x] done

### Step 2. Health endpoint

- Kind: code
- Tests first: `backend/tests/unit/api/test_health.py`: `GET /api/health` returns 200 and `{"status": "ok", "version": <package version>}`; the OpenAPI schema lists `/api/health` with the `HealthResponse` schema. App built with `create_app` and test settings (`tmp_path` as data dir).
- Change: `app.py` (`create_app`), `settings.py` (minimal), `api/schemas.py`, `api/routes/health.py`.
- Done when: tests pass, `make check` green.
- [x] red
- [x] green

### Step 3. Settings fail fast

- Kind: code
- Tests first: `backend/tests/unit/test_settings.py`: without `ASSISTANT_DATA_DIR`, loading `Settings` raises an error whose message names `ASSISTANT_DATA_DIR`; with it set, `data_dir` is a `Path`; unknown `ASSISTANT_` variables are ignored.
- Change: `settings.py` (`load_settings`, `SettingsError`), `main` factory in `app.py`, `.env.example`.
- Done when: tests pass, `make check` green.
- [x] red
- [x] green

### Step 4. Layer contract

- Kind: code
- Tests first: `backend/tests/architecture/test_layers.py`: (a) the import contract passes for the real package; (b) a copy of the package in `tmp_path` with an added `services/_violation.py` that imports `assistant.adapters` makes `lint-imports` fail, and the output names that import; (c) the same for `domain/_violation.py` importing `fastapi` (the domain stays free of frameworks). Red because no contract is configured yet.
- Change: import-linter configuration in `pyproject.toml` with the layers from ADR 0002 (`api` → `services` → `ports` | `domain`; `adapters` → `ports` | `domain`; only `app` imports `adapters`); `lint-imports` added to `check-backend`.
- Done when: tests pass, `make check` green.
- [x] red
- [x] green

### Step 5. Scaffold the frontend project

- Kind: setup
- Change: `frontend/` Vite React TypeScript project with packages from ADR 0011, `tsconfig` strict with `noUncheckedIndexedAccess`, ESLint flat config (typescript-eslint strict, react-hooks, jsx-a11y), Prettier, Tailwind, Vitest with jsdom and Testing Library setup, `.nvmrc` (24), Vite proxy `/api` → `http://localhost:8000`; Makefile `check-frontend` (prettier --check, eslint, tsc, vitest), `dev`, `setup`.
- Done when: `make check` and `make dev` run (default Vite page served, API reachable through the proxy).
- Commit: `build(frontend): scaffold Vite React project with lint, types and tests`
- [x] done

### Step 6. Generated API client and contract check

- Kind: setup
- Change: `assistant/openapi.py` (prints schema), Makefile `api-client`, generated `frontend/src/api/openapi.json` and `schema.d.ts`, `frontend/src/api/client.ts`, `scripts/ci/check-api-client.sh` (regenerates into a temporary directory and diffs), included in `make check`.
- Done when: `make check` green; changing `HealthResponse` locally without regenerating makes `scripts/ci/check-api-client.sh` fail (checked by hand, change reverted, result noted in the review).
- Commit: `build(api): generate the TypeScript client from the OpenAPI schema`
- [x] done (verified 2026-10-28: adding a field to `HealthResponse` without regenerating fails the check with a diff of both files; passes again after reverting)

### Step 7. API status in the app shell

- Kind: ui
- Tests first: `frontend/src/features/status/ApiStatus.test.tsx` with msw: when `/api/health` returns ok, the shell shows "API: ok" and the version; when the request fails or returns 5xx, it shows "API: unavailable"; while loading, it shows "API: checking". Accessible: the status is a `role="status"` element.
- Change: `useApiHealth.ts`, `ApiStatus.tsx`, `App.tsx` shell, `main.tsx` with `QueryClientProvider`; default Vite demo content removed.
- Done when: tests pass, `make check` green, and with `make dev` the page shows "API: ok".
- [x] red
- [x] green

### Step 8. Git hooks

- Kind: setup
- Change: `.pre-commit-config.yaml` with local hooks: ruff format, ruff check, mypy for `backend/`; Prettier, ESLint, tsc for `frontend/`; no test hooks. `make setup` runs `uvx pre-commit install`.
- Done when: a commit with a formatting error is fixed or rejected by the hook; a commit with a failing test is accepted.
- Commit: `build: run format, lint and type checks before each commit`
- [x] done (verified 2026-10-28: a badly formatted Python file is reformatted and the commit stopped; a commit adding a failing test is accepted)

### Step 9. CI jobs for code

- Kind: setup
- Change: `ci.yml` jobs `Backend` (setup-uv, `make check-backend`), `Frontend` (setup-node from `.nvmrc`, pnpm, `make check-frontend`), `API contract` (both toolchains, `scripts/ci/check-api-client.sh`). Actions pinned to SHAs. `ADR 0010` table unchanged (it already lists these jobs).
- Done when: all six jobs pass on the pull request.
- Commit: `ci: check backend, frontend and API contract`
- [x] done (workflow linted locally; the jobs are proven by the pull request run)

### Step 10. Developer documentation

- Kind: setup
- Change: README "Getting started" (prerequisites, `make setup`, `make dev`, `make check`); root `CLAUDE.md` and project `CLAUDE.md` files drop "scaffolded in F-00" notes.
- Commit: `docs(F-00): document development setup`
- [x] done

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 `make setup` + `make check` pass | 1, 5, 6, 8 (and CI in 9) |
| AC-2 health endpoint and schema | 2 |
| AC-3 layer violation fails the check | 4 |
| AC-4 status in the UI, ok and unavailable | 7 |
| AC-5 stale client fails CI | 6, 9 |
| AC-6 `make dev` ports, proxy, reload | 5, 7 |
| AC-7 pre-commit without tests | 8 |
| AC-8 new CI jobs pass | 9 |
| AC-9 missing setting fails with its name | 3 |

## After merge

Add `Backend`, `Frontend` and `API contract` to the required checks of `main` (repository settings, done by the human).
