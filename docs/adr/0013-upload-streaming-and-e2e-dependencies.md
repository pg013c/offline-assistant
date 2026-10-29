# 0013. Dependencies for uploads, streamed answers and end-to-end tests

- Status: accepted
- Date: 2026-10-28
- Related: GEN-30, ADR 0005, ADR 0011, F-01

## Context

F-01 adds file uploads, answers streamed as Server-Sent Events over `POST`, and the first browser journey. FastAPI 0.162 already ships SSE support (`fastapi.sse.EventSourceResponse`, with the event schema in OpenAPI as `itemSchema`), so the backend needs no SSE library. Three gaps remain:

- FastAPI parses multipart form data only with `python-multipart` installed.
- The browser `EventSource` API supports `GET` only; a question is sent with `POST`, so the UI reads the stream with `fetch` and needs an SSE parser.
- The spec asks for a Playwright journey in CI (AC-10).

## Decision

| Package | Side | Purpose | Licence |
|---|---|---|---|
| python-multipart | backend runtime | multipart uploads in FastAPI | Apache-2.0 |
| eventsource-parser | frontend runtime | parse the SSE stream read with `fetch` (FE-12) | MIT |
| @playwright/test | frontend development | browser journeys in `frontend/e2e/` | Apache-2.0 |

Playwright downloads its browser (Chromium only) in `make setup` and in CI. This is a development-time download; the running product needs no browser and stays offline (ADR 0004).

## Alternatives considered

- **`GET /api/chat?question=...` with `EventSource`** – no parser needed, but puts user questions into URLs and server logs, and caps their length.
- **Hand-written SSE parser** – about 30 lines, but the format has edge cases (multi-line data, comments, `retry`) that a maintained, dependency-free parser already handles.
- **sse-starlette** – unnecessary now that FastAPI supports SSE natively.
- **Cypress** – heavier, and Playwright's `webServer` option starts the API and UI for the journey with no extra tooling.

## Consequences

- Good: each addition is small, permissively licensed and has no runtime network access.
- Bad: CI gets a slower job (`E2E`) that installs Chromium.
- Follow-up: `E2E` becomes a required check on `main` after F-01 merges.
