# 0014. Browser journeys run against the real API

- Status: accepted
- Date: 2026-10-29
- Related: ADR 0006, ADR 0013, F-01, [testing.md](../standards/testing.md)

## Context

`testing.md` planned UI journeys with Playwright against a fake backend, inside `make check`. Building F-01 showed two things. Component tests with msw already cover the UI against a mocked API; a journey against another mock would add little. And the riskiest parts of the walking skeleton are the integrations a mock hides: multipart upload, the SSE stream through the Vite proxy, and the generated client.

## Decision

- Browser journeys run against the real API, started by Playwright, with the deterministic test model and a fresh temporary data directory per run.
- They run with `make e2e` and in their own CI job (`E2E`, a required check), not in `make check`, because they start servers and a browser.
- Journeys stay few (one to three golden paths). Behaviour details stay in component and API tests.
- Once real models arrive (F-06), journeys keep using the test model, so they stay fast and deterministic; model behaviour is measured by evaluations (ADR 0006).

## Alternatives considered

- **Fake backend, as first planned** – duplicates what the msw component tests cover and misses the integration bugs journeys are for.
- **Journeys inside `make check`** – makes the everyday check slow and dependent on a browser install.

## Consequences

- Good: the one path a user takes is tested end to end, including upload and streaming.
- Bad: journeys need uv, Node and Chromium; the `E2E` job is the slowest in CI.
- Follow-up: `testing.md` updated in the same change.
