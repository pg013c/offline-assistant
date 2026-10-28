# F-00. Review

- Reviewed range: `main...feat/F-00-repository-skeleton` at `5e581a6`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: not applicable (no model behaviour)
- Checks: `make check` passes (ruff, mypy, 3 import contracts, 10 backend tests, prettier, eslint, tsc, 4 UI tests, API contract). Red commits add only tests and stubs; green commits touch no test paths.
- Verification: all 11 findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `backend/src/assistant/` | The spec's scope includes structlog setup, but no logging configuration exists; each later feature would configure logging its own way. | Spec scope, PY-15 | fix |
| 2 | major | `Makefile:9-10` | `ASSISTANT_DATA_DIR ?= data/storage` gives the required setting a silent default, so `make dev` never hits the fail-fast path and writes to `./data/storage` without `.env`. | GEN-20, AC-9 | fix |
| 3 | minor | `Makefile:8-10` | `-include .env` exports only three variables; other `ASSISTANT_*` values in `.env` would not reach the API, and quoted values keep their quotes. | Plan design (`make dev` loads `.env`) | fix |
| 4 | minor | `backend/pyproject.toml:77-81` | The `pure-domain` contract claims "standard library and Pydantic only" but forbids five named packages, and does not cover `services`, so a service could import a model or database library. | ADR 0002, PY-04 | fix |
| 5 | minor | `backend/pyproject.toml:70-74` | `adapters-only-in-app` does not cover `assistant.settings` and `assistant.openapi`, which sit outside the layer list. | PY-04 | fix |
| 6 | minor | `frontend/src/features/status/ApiStatus.test.tsx` | Only `ApiStatus` is tested; removing it from the `App` header would still pass. | AC-4, TEST-09 | fix |
| 7 | minor | `frontend/src/main.tsx:13` | Production `QueryClient` retries three times with backoff, so an unreachable API shows "checking" for about 7 s before "unavailable"; tests disable retries, so this is never exercised. | AC-4 | fix |
| 8 | note | `backend/src/assistant/settings.py:28` | `issue['loc'][0]` raises `IndexError` for errors without a location (e.g. a future model validator) and drops nested path segments. | GEN-21 | fix |
| 9 | note | `Makefile:37` | `trap 'kill 0'` signals the whole process group; run without job control (scripts, agent tools) it also kills the caller. | – | fix |
| 10 | note | `spec.md` | TEST-09 asks for the acceptance-criteria mapping in `spec.md`; it is in `plan.md`. AC-5, AC-6 and AC-7 are verified by hand only. | TEST-09 | fix |
| 11 | note | `backend/pyproject.toml:21-26` | Starlette warns that `httpx` in the test client is deprecated in favour of `httpx2`. | ADR 0011 | backlog (follow-up chore) |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `ed1d05e` test, `b791d36` fix |
| 2 | `301704f` test, `fab173b` fix |
| 3 | `c94c016` fix (Makefile only, verified by hand: a variable from the env file reaches the recipe environment) |
| 4 | `c987160` test, `92a6364` fix |
| 5 | `c987160` test, `92a6364` fix |
| 6 | `f2e000c` test (characterisation; fails when `<ApiStatus />` is removed from the header) |
| 7 | `ffe069d` test, `7b0cda6` fix |
| 8 | `2ca53d1` test, `e28c7aa` fix |
| 9 | `c94c016` fix (verified by hand: Ctrl-C to the group and TERM to the recipe shell both stop API and UI; the caller is not signalled) |
| 10 | `3ba897f` docs |
| 11 | moved to [backlog follow-ups](../../backlog.md#follow-ups) in `3ba897f` |
