# F-01. Review

- Reviewed range: `main...feat/F-01-walking-skeleton` at `9e41f14`
- Reviewer: `reviewer` agent, fresh context (findings 1–16); findings 17–18 were raised by the implementer before review
- Evaluation: not applicable (deterministic fake model; evaluations start with F-04)
- Checks: `make check` passes (4 import contracts, 74 backend tests, 20 UI tests, API contract) and `make e2e` passes. Red commits precede green ones; green commits touch no test paths.
- Verification: all 16 reviewer findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `backend/src/assistant/api/schemas.py:20-24` | `ErrorResponse` has no `details` field, so the error body differs from the standard and adding it later breaks the contract. | PY-22, AC-2 | fix |
| 2 | major | `backend/src/assistant/api/routes/documents.py:35` | The whole upload is read into memory before the 5 MB check; a huge file can exhaust memory before it gets its 413. | GEN-42 | fix |
| 3 | major | `services/documents.py:40`, `services/questions.py:41`, `adapters/file_document_store.py:23-24` | Every upload and question lists documents through `load_all()`, reading every stored file synchronously inside async handlers. | PY-14 | fix |
| 4 | major | `frontend/src/features/chat/useChatStream.ts:85` | A stream that ends without an `end` event leaves the UI in `streaming` with the Ask button disabled. | FE-12 | fix |
| 5 | minor | `backend/src/assistant/api/errors.py:28-29` | Request validation errors return FastAPI's default `{"detail": [...]}` instead of the standard body. | PY-22 | fix |
| 6 | minor | `backend/src/assistant/api/errors.py:22` | Exact-type lookup behind `# type: ignore`: a new `DocumentRejected` subclass without an entry becomes a 500. | PY-22 | fix |
| 7 | minor | `backend/src/assistant/api/routes/chat.py:35-36` | `case _` treats any event as the end event; a new event type would fail at runtime mid-stream, not in type checking. | PY-03 | fix |
| 8 | minor | `settings.py:17`, `app.py:33` | `ASSISTANT_CHAT_MODEL` is declared and documented but never read; the fake model is hard-wired. | GEN-05 | fix |
| 9 | minor | `frontend/src/features/chat/ChatView.tsx:7` | The UI decides a model is a test model by its name. | AI-23, AC-8 | fix |
| 10 | minor | `frontend/src/features/chat/CitationDialog.tsx:13-14` | Non-modal `<dialog open>`: focus is not moved or returned, and Escape does not close it. | FE-24 | fix |
| 11 | minor | `frontend/src/features/chat/useChatStream.ts:9, 51-58` | The SSE event union is written by hand; only its three variants are generated. | FE-10, AC-6 | fix |
| 12 | minor | `test_question_service.py:79`, `test_chat_api.py:65` | Tests check that a quote appears in the document, not in the cited chunk. | AC-4, TEST-09 | fix |
| 13 | minor | `adapters/fakes/chat_model.py:9`, `domain/answers.py:8` | The sentence-splitting pattern and "two sentences" rule are duplicated, so the answer and its quote can drift apart. | GEN-01 | fix |
| 14 | note | `frontend/playwright.config.ts:11` | Every config load creates a temporary data directory that is never removed. | – | fix |
| 15 | note | `docs/standards/testing.md:16` | The standard still says UI journeys use a fake backend and run in `make check`; spec decision 4 changed that. | – | fix |
| 16 | note | `test_documents_api.py:13-14`, `test_chat_api.py:18-19` | Route tests use the real file-backed composition root rather than fake services. | testing.md | backlog (F-03) |
| 17 | note | `frontend/src/test/setup.ts:1` | The Node types reference in the test setup also makes Node types visible to application code in the same TypeScript project. | FE-01 | fix |
| 18 | note | `frontend/src/features/chat/ChatView.tsx` | The UI does not use `found=false`; the "no relevant passage" notice is plain answer text. | – | backlog (F-07) |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `eb8a25c` test, `bbd9bd7` fix |
| 2 | `0ca680f` test, `24f557c` fix |
| 3 | `7b43b1c` test, `df50663` fix |
| 4 | `427cfd5` test, `67b3f77` fix |
| 5 | `eb8a25c` test, `bbd9bd7` fix |
| 6 | `de362f1` test, `103bf58` fix |
| 7 | `cfc2073` fix (exhaustive match ending in `assert_never`; checked by mypy) |
| 8 | `ba60fbd` fix (adapter chosen from `ASSISTANT_CHAT_MODEL`; covered by existing tests) |
| 9 | `641363d` test, `98d1960` fix |
| 10 | `5836c17` test, `5efb959` fix (modal in browsers; journey still passes) |
| 11 | `7d6779e` test, `cfc2073` fix |
| 12 | `cfb6dbc` test (tightened; code already correct) |
| 13 | `3100f80` refactor |
| 14 | `5125139` build (one directory per run, removed in global teardown; checked by counting directories) |
| 15 | `b2a16af` docs: ADR 0014 and `testing.md` |
| 16 | moved to [backlog follow-ups](../../backlog.md#follow-ups) for F-03 in `b2a16af` |
| 17 | `0b4893a` build (tests in their own TypeScript project; `process` in `src/` is a type error) |
| 18 | moved to [backlog follow-ups](../../backlog.md#follow-ups) for F-07 in `b2a16af` |
