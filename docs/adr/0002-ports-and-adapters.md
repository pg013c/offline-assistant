# 0002. Ports and adapters for every model-backed capability

- Status: accepted
- Date: 2026-10-28
- Related: FR-40, FR-43, ADR 0003, ADR 0006

## Context

The point of the project is to swap and compare models: several LLMs, embedding models, with and without a reranker, different speech engines. Model libraries are heavy, slow to load and non-deterministic, which makes code that calls them directly hard to test. We also want the business logic (retrieval, citation checking, refusal, tool handling) to be testable in milliseconds.

## Decision

Hexagonal architecture in the backend:

- `domain/`: entities and pure rules. Depends only on the standard library and Pydantic.
- `ports/`: one `typing.Protocol` per capability: `ChatModel`, `Embedder`, `Reranker`, `VectorStore`, `DocumentParser`, `SpeechToText`, `TextToSpeech`, `NoteStore`.
- `services/`: use cases. Depend on `ports` and `domain` only.
- `adapters/`: implementations. The only layer that imports model, database or parsing libraries.
- `api/`: FastAPI routes and request/response schemas. Calls `services`.
- `app.py`: the composition root. Reads settings and wires adapters into services.

Every port has a fake adapter in `adapters/fakes/` that is deterministic and fast. Unit tests use fakes. Integration tests use real adapters and are marked so they can run separately.

Import direction is enforced by a test (import-linter contract), not only by review.

## Alternatives considered

- **LangChain or LlamaIndex as the backbone** – fast to start, but hides the parts we want to show and measure (retrieval, retries, citation checks) and couples the code to a fast-moving API. Individual components may still be used inside an adapter.
- **Plain layered app without ports** – fewer files, but every service test would load real models or need ad-hoc mocks.

## Consequences

- Good: swapping a model is a configuration change plus, at most, one new adapter.
- Good: services are tested with fakes in milliseconds; real models are tested at the edges and by evaluations.
- Bad: more files and indirection than a script. Acceptable: the indirection is exactly what the evaluation work needs.
- Follow-up: import-linter contract in `backend/`, rules in [python.md](../standards/python.md).
