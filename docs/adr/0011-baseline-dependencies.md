# 0011. Baseline dependencies

- Status: accepted
- Date: 2026-10-28
- Related: GEN-30, ADR 0001, ADR 0002, ADR 0005, ADR 0008, F-00

## Context

GEN-30 requires an ADR for every runtime dependency, with its licence. F-00 creates both projects, so it needs the foundation libraries that the earlier ADRs and the standards already assume (FastAPI, Pydantic, structlog, TanStack Query, the OpenAPI client generator), plus the tooling the standards name. Recording them once here keeps later ADRs about the libraries that are real choices (Docling, Qdrant client, Whisper, Piper).

## Decision

### Backend runtime

| Package | Purpose | Licence |
|---|---|---|
| fastapi | HTTP API, OpenAPI schema (ADR 0005) | MIT |
| uvicorn | ASGI server | BSD-3-Clause |
| pydantic | domain and API models | MIT |
| pydantic-settings | typed settings (PY-13) | MIT |
| structlog | structured logging (PY-15) | MIT or Apache-2.0 |

### Backend development

pytest (MIT), httpx (BSD-3-Clause, ASGI test client), mypy (MIT), ruff (MIT), import-linter (BSD-2-Clause, PY-04), pre-commit (MIT, run with `uvx`, not a project dependency).

### Frontend runtime

| Package | Purpose | Licence |
|---|---|---|
| react, react-dom | UI (ADR 0008) | MIT |
| @tanstack/react-query | server state (FE-11) | MIT |
| openapi-fetch | typed client over the generated schema (ADR 0005) | MIT |

### Frontend development

vite and @vitejs/plugin-react (MIT), typescript (Apache-2.0), tailwindcss and @tailwindcss/vite (MIT), eslint, typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-jsx-a11y (MIT), prettier (MIT), vitest (MIT), @testing-library/react, @testing-library/jest-dom, @testing-library/user-event (MIT), jsdom (MIT), msw (MIT, HTTP mocking at the network boundary in UI tests), openapi-typescript (MIT).

### Toolchain versions

Python 3.13 (managed by uv), Node 24 LTS (pinned in `.nvmrc`), pnpm 11. Exact package versions are locked in `uv.lock` and `pnpm-lock.yaml`.

React Router is deferred to F-08: the UI has one view until then.

## Alternatives considered

- **One ADR per package** – noise for libraries that follow directly from earlier decisions.
- **No record, rely on lock files** – lock files show versions, not why a package is there or whether its licence fits (NFR-07).
- **Biome instead of ESLint and Prettier** – faster and one tool, but jsx-a11y coverage is the reason for ESLint here (FE-02, FE-24).

## Consequences

- Good: every package in the first lock files has a recorded purpose and licence; all are permissive.
- Follow-up: the README licence section lists runtime dependencies once the showcase is written (F-15).
