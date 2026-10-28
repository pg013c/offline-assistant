# 0001. Monorepo with a Python backend and a React frontend

- Status: accepted
- Date: 2026-10-28
- Related: FR-50, FR-60

## Context

The system has a Python backend (the model ecosystem is Python-first: Docling, faster-whisper, Piper, sentence-transformers, Qdrant client) and a browser UI. One person builds it, with a coding agent, in a few weeks. The API contract between the two changes often in the early milestones.

## Decision

One repository with two independent projects:

- `backend/`: a uv-managed Python project, package `assistant`.
- `frontend/`: a pnpm-managed React project.

There is no shared build system across them. A root `Makefile` is the single entry point (`make dev`, `make test`, `make check`, `make eval`, `make offline-check`) and delegates to each project's own tooling. Each project has its own `CLAUDE.md` with stack-specific rules.

## Alternatives considered

- **Two repositories** – contract changes need two coordinated pull requests; a reviewer cannot see a feature in one place.
- **Monorepo tooling (Nx, Turborepo, Pants)** – solves problems we do not have at this size and mixes ecosystems poorly.
- **Python-only UI (Streamlit, Gradio)** – fast, but a weak showcase of a production-style split and limited control over streaming and audio.

## Consequences

- Good: one pull request per feature, end to end; one CI pipeline; one place for docs.
- Good: each half uses its ecosystem's standard tools, nothing custom.
- Bad: two toolchains to install (uv, pnpm). Documented in the README.
