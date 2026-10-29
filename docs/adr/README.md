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
| [0007](0007-native-model-serving-on-macos.md) | Native model serving on macOS | accepted |
| [0008](0008-vite-spa-frontend.md) | Vite single-page app instead of a server-rendered framework | accepted |
| [0009](0009-test-first-commits-and-merge-strategy.md) | Test-first commits, kept in history | accepted |
| [0010](0010-continuous-integration-from-the-first-commit.md) | Continuous integration from the first commit | accepted |
| [0011](0011-baseline-dependencies.md) | Baseline dependencies | accepted, amended by 0012 |
| [0012](0012-frontend-toolchain-versions.md) | Frontend toolchain versions | accepted |
| [0013](0013-upload-streaming-and-e2e-dependencies.md) | Dependencies for uploads, streamed answers and end-to-end tests | accepted |
| [0014](0014-browser-journeys-against-the-real-api.md) | Browser journeys run against the real API | accepted |
