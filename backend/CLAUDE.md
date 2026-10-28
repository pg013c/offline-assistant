# Backend

Python 3.13, uv, FastAPI, Pydantic v2. Package `assistant` in `src/assistant/`.

Rules: [../docs/standards/python.md](../docs/standards/python.md), [../docs/standards/ai.md](../docs/standards/ai.md), [../docs/standards/testing.md](../docs/standards/testing.md).

- Layers: `api → services → ports/domain`; `adapters` implement `ports`; only `app.py` wires adapters. Checked by import-linter.
- New capability that needs a model, database or parser: add a port (Protocol), a fake adapter, a contract test, then the real adapter.
- Unit tests use fakes and do no I/O. Real adapters are tested in `tests/integration/` with the `integration` marker.
- Prompts are files in `src/assistant/prompts/`.
- Run everything with `uv run ...`; add dependencies with `uv add` only after an ADR.
