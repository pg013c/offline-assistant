# Testing standards

How each part of the system is verified ([ADR 0006](../adr/0006-tdd-for-code-evals-for-model-behaviour.md)) and how tests are written. The red/green commit loop is described in [workflow.md](../workflow.md).

## What is tested how

| Part | Check | Tooling | Runs in |
|---|---|---|---|
| Domain, services, tools, retries, citation checks | unit tests, test first | pytest + fakes | `make check`, every push |
| Adapters (Qdrant, Docling, Whisper, chat server) | integration and port contract tests | pytest, marker `integration` | `make check` locally, CI with services |
| API | route tests over the ASGI app with fake services | pytest + httpx | `make check` |
| API contract | generated client is up to date | `make api-client` + diff | `make check` |
| Model behaviour (answers, citations, refusals, tool choice) | evaluation cases, written first | Promptfoo | `make eval`, on demand |
| Retrieval quality | recall@k and MRR against expected chunks | Promptfoo / pytest | `make eval` |
| UI logic and state | component and hook tests | Vitest + Testing Library | `make check` |
| UI journeys | 1–3 golden paths | Playwright, fake backend | `make check` |
| Offline guarantee | end-to-end suite with networking disabled | Docker Compose | `make offline-check` (from F-10) |
| Performance | TTFT, tokens/s, memory | measurement script | `make bench`, on demand |

## Rules

- **TEST-01** A test describes behaviour, not implementation. Names read as sentences: `test_refuses_when_no_chunk_is_relevant`.
- **TEST-02** Arrange, act, assert, separated by blank lines. One behaviour per test; several asserts about that behaviour are fine.
- **TEST-03** Unit tests use the fakes from `adapters/fakes/`, not `unittest.mock` patches of internals. Mocks are acceptable only to simulate failures a fake cannot produce.
- **TEST-04** Unit tests do no I/O: no network, no disk outside `tmp_path`, no model loading. The suite runs in seconds.
- **TEST-05** Every port has a contract test that every adapter, including the fake, must pass. A fake that diverges from the real adapter is a bug.
- **TEST-06** Tests are deterministic. Time, randomness and ids are injected. Flaky tests are fixed or deleted the same day, never retried into passing.
- **TEST-07** Fixtures are small, hand-written documents (a few articles) in `tests/fixtures/`. Full legal texts are used only in integration and evaluation runs.
- **TEST-08** In the green phase, test files are not edited (ADR 0009). A wrong test goes back to red in its own commit.
- **TEST-09** No coverage target. Every acceptance criterion maps to at least one test or evaluation case, recorded in `spec.md`.

## Evaluation cases

- **TEST-20** Each case has: id, language, question, expected source chunk ids (or `none` for out-of-scope), expected behaviour (`answer`, `refuse`, `tool:<name>`), and optional reference answer.
- **TEST-21** The dataset covers both languages, out-of-scope questions, cross-article questions, and prompt-injection documents.
- **TEST-22** Dataset files are not edited in the same commit as the code or prompt they evaluate.
- **TEST-23** LLM-as-judge assertions use a fixed judge model and a written rubric committed with the dataset. Judge results are spot-checked by hand when a metric moves by more than 5 points.
