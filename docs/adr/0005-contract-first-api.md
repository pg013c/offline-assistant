# 0005. Contract-first API with a generated TypeScript client

- Status: accepted
- Date: 2026-10-28
- Related: ADR 0001, ADR 0008

## Context

The backend is Python, the frontend TypeScript. Hand-written fetch calls and duplicated types drift apart, and a coding agent working on one side does not see the other.

## Decision

- FastAPI with Pydantic models is the source of the OpenAPI schema.
- The schema is exported to `frontend/src/api/openapi.json` by `make api-client`, and TypeScript types and a typed client are generated from it (`openapi-typescript` + `openapi-fetch`).
- Generated files are committed. CI regenerates them and fails if the result differs (the contract check).
- The frontend calls the backend only through the generated client.
- Streaming endpoints (chat, speech) use Server-Sent Events. Their event payloads are Pydantic models included in the schema, so they are typed on both sides too.

## Alternatives considered

- **Hand-written types** – drift is guaranteed.
- **GraphQL or tRPC** – tRPC needs TypeScript on both sides; GraphQL is overhead for a dozen endpoints.
- **WebSockets for chat** – bidirectional is not needed; SSE is simpler, works with plain HTTP and is easy to test.

## Consequences

- Good: a backend change that breaks the UI fails in CI, not in the browser.
- Good: the agent working on the frontend reads exact types instead of guessing.
- Bad: one extra generation step after each API change. It is part of the `/tdd` skill's checklist.
