# Architecture Decision Records

One file per decision, numbered, never renumbered. A record is not edited after it is accepted, except to change its status. A changed decision gets a new record that supersedes the old one.

Write a record when a decision:

- is hard or expensive to reverse,
- adds a dependency, a model, a service or a protocol,
- changes a rule in [../standards/](../standards/),
- or would make a new contributor ask "why is it like this?".

Use the `/adr` skill or copy [template.md](template.md).

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-monorepo-python-backend-react-frontend.md) | Monorepo with a Python backend and a React frontend | accepted |
| [0002](0002-ports-and-adapters.md) | Ports and adapters for every model-backed capability | accepted |
| [0003](0003-openai-compatible-llm-interface.md) | OpenAI-compatible API as the only LLM interface | accepted |
| [0004](0004-offline-first-no-egress.md) | Offline first: no network egress at runtime | accepted |
| [0005](0005-contract-first-api.md) | Contract-first API with a generated TypeScript client | accepted |
| [0006](0006-tdd-for-code-evals-for-model-behaviour.md) | TDD for code, evaluations for model behaviour | accepted |
| [0007](0007-native-model-serving-on-macos.md) | Native model serving on macOS | accepted, amended by 0021 |
| [0008](0008-vite-spa-frontend.md) | Vite single-page app instead of a server-rendered framework | accepted |
| [0009](0009-test-first-commits-and-merge-strategy.md) | Test-first commits, kept in history | accepted |
| [0010](0010-continuous-integration-from-the-first-commit.md) | Continuous integration from the first commit | accepted |
| [0011](0011-baseline-dependencies.md) | Baseline dependencies | accepted, amended by 0012 |
| [0012](0012-frontend-toolchain-versions.md) | Frontend toolchain versions | accepted |
| [0013](0013-upload-streaming-and-e2e-dependencies.md) | Dependencies for uploads, streamed answers and end-to-end tests | accepted |
| [0014](0014-browser-journeys-against-the-real-api.md) | Browser journeys run against the real API | accepted |
| [0015](0015-document-parsing-with-docling-and-tesseract.md) | Parse documents with Docling and Tesseract, models fetched ahead of time | accepted, amended by 0016 |
| [0016](0016-docling-dependencies-and-pinned-models.md) | Docling's dependencies and pinned parsing models | accepted |
| [0017](0017-qdrant-and-bge-m3-for-hybrid-search.md) | Hybrid search with BGE-M3 embeddings and BM25 in Qdrant | accepted |
| [0018](0018-promptfoo-and-a-pinned-evaluation-corpus.md) | Evaluate with Promptfoo on a corpus pinned by hash | accepted |
| [0019](0019-bge-reranker-v2-m3-for-reranking.md) | Rerank with BGE reranker v2 M3, pinned and loaded offline | accepted |
| [0020](0020-retrieval-targets.md) | Retrieval targets: floors that `make eval` enforces | accepted |
| [0021](0021-llama-server-and-qwen3-8b.md) | Serve the local LLM with llama.cpp's llama-server, starting with Qwen3 8B | accepted |
| [0022](0022-local-judge-and-answer-floors.md) | Judge answers with a local Qwen3 30B-A3B, and floor citation support and tool-call validity | accepted, amended by 0023 |
| [0023](0023-the-judge-thinks.md) | The judge thinks before it rules | accepted |
