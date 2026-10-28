# Python standards

Applies to `backend/`. Enforced by `make check` in `backend/`.

## Toolchain

- **PY-01** Python 3.13, managed by `uv`. Dependencies in `pyproject.toml`, locked in `uv.lock`. No `pip install`, no `requirements.txt`.
- **PY-02** `ruff format` and `ruff check` (rule sets: E, F, I, B, UP, SIM, RUF, PL, S, ASYNC). Zero warnings.
- **PY-03** `mypy --strict` passes. `Any` only at third-party boundaries inside adapters, with a comment.
- **PY-04** Layer imports are checked by `import-linter` (ADR 0002): `api → services → ports/domain`; `adapters → ports/domain`; nothing imports `adapters` except `app.py`.

## Code

- **PY-10** Type hints on every function signature, including return types. Prefer `collections.abc` types and `X | None`.
- **PY-11** Ports are `typing.Protocol` classes in `ports/`. Adapters do not inherit from them; conformance is checked by mypy and by a contract test per port.
- **PY-12** Domain objects are Pydantic models (frozen where they are values) or `@dataclass(frozen=True, slots=True)`. API schemas are separate Pydantic models in `api/schemas.py`; services do not return API schemas.
- **PY-13** Settings via `pydantic-settings`, one `Settings` class, prefix `ASSISTANT_`.
- **PY-14** I/O-bound code is `async`. CPU- or GPU-bound model calls in adapters run in a thread or process pool, never blocking the event loop.
- **PY-15** No `print`. Logging with `structlog`, structured key-value events, one logger per module.
- **PY-16** No bare `except`, no `except Exception: pass`. Catch the narrowest exception that the code can handle.
- **PY-17** Functions longer than ~40 lines or with more than ~4 levels of nesting are split, unless a comment explains why not.
- **PY-18** Public functions of `services` and `ports` have a one-line docstring stating the contract, not the implementation.

## FastAPI

- **PY-20** Routes are thin: validate input, call one service method, map the result to a schema. No business logic in routes.
- **PY-21** Dependencies (services) are injected with `Depends` from the composition root, never constructed inside a route.
- **PY-22** Errors map to HTTP via exception handlers in one place, with a stable error body (`code`, `message`, `details`).
- **PY-23** Streaming responses use SSE with typed event models included in the OpenAPI schema (ADR 0005).

## Layout

```text
backend/
├── pyproject.toml
├── src/assistant/
│   ├── app.py            composition root
│   ├── settings.py
│   ├── domain/
│   ├── ports/
│   ├── services/
│   ├── adapters/
│   │   └── fakes/
│   └── api/
└── tests/
    ├── unit/             fakes only, no I/O, milliseconds
    ├── integration/      real adapters, marked `integration`
    └── contract/         one per port: every adapter, fake included, passes it
```
