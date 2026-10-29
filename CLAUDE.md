# Offline Assistant

A knowledge assistant that runs entirely on one machine: local LLM with tools, RAG with citations, voice in and out, measured against a cloud model. Python (FastAPI) backend, React frontend.

## Read first

- What and why: [docs/prd.md](docs/prd.md)
- System shape: [docs/architecture.md](docs/architecture.md), decisions in [docs/adr/](docs/adr/)
- How work is done: [docs/workflow.md](docs/workflow.md)
- Rules you apply and are reviewed against: [docs/standards/](docs/standards/)
- What is next: [docs/backlog.md](docs/backlog.md)

Stack-specific rules: [backend/CLAUDE.md](backend/CLAUDE.md), [frontend/CLAUDE.md](frontend/CLAUDE.md).

## Non-negotiable

1. **English only** in code, comments, docs, commit messages and UI copy.
2. **Test first.** Every plan step is a red commit (tests) and then a green commit (code). In the green phase, never edit tests. See ADR 0009.
3. **Model behaviour is evaluated, not unit-tested.** Prompt, tool schema, retrieval or model changes need evaluation cases first and an eval run (ADR 0006).
4. **Offline.** No runtime downloads, no telemetry, no network calls except the cloud adapter in comparison mode (ADR 0004).
5. **Layers.** Services depend on ports, never on adapters (ADR 0002).
6. **No new dependency, model or standard change without an ADR.**
7. **The human merges.** Never push to `main`, never merge, never force-push.

## Working state lives in files

A feature's intent is in `docs/features/F-xx-*/spec.md`, its steps in `plan.md`, its review in `review.md`. Start from those, not from memory. Tick plan steps as you finish them.

## Commands

| Command | Does |
|---|---|
| `make dev` | API and UI with hot reload |
| `make check` | format, lint, types, unit tests, API contract |
| `make test-integration` | tests with real adapters (needs `make models`) |
| `make test` | tests only |
| `make eval` | evaluation suite (needs a running model server) |
| `make api-client` | regenerate the TypeScript client from OpenAPI |
| `make offline-check` | end-to-end with networking disabled |

`make eval` arrives with F-04 and `make offline-check` with F-10. `make help` lists what exists now. Use Node from `.nvmrc` (`nvm use`).

## Skills

`/spec`, `/adr`, `/plan-feature`, `/tdd`, `/eval-run`, `/review-branch`, `/ship`. Which one when: [docs/workflow.md §3](docs/workflow.md#3-feature-track).

## Commits

Conventional Commits, scope = module. Trailers: `Refs: F-xx` and `Co-Authored-By`. Examples in [docs/workflow.md §4](docs/workflow.md#4-the-redgreen-loop).
