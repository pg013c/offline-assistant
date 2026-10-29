# F-03. Review

- Reviewed range: `main...feat/F-03-hybrid-search` at `d199eba`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: not applicable as a run (F-04 builds the harness); fixed retrieval cases in `tests/integration/test_hybrid_search.py` pass
- Checks: `make check` (4 import contracts, 186 backend tests, 41 UI tests, API contract), `make test-integration` (43) and `make e2e` (2) pass. Red commits precede green ones; green commits touch no test paths.
- Verification: all 17 findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `services/documents.py:93-130`, `:132-152` | `ingest` writes chunks, vectors and status without the lock, so a delete or re-index during a running parse is undone: a deleted document comes back `ready` and citable, or is written back as `failed`. | AC-5, AC-6 | fix |
| 2 | major | `services/questions.py:40`, `api/routes/chat.py` | The async answer stream calls the blocking search (BGE-M3 encoding, Qdrant HTTP) on the event loop; the first question also loads 2 GB of weights, stalling every other request. | PY-14 | fix |
| 3 | minor | `app.py:107` | `restore()` runs inside the lifespan; rebuilding an empty collection embeds every stored chunk before the server answers, which can time out health checks. | PY-14, AC-7 | fix |
| 4 | minor | `services/questions.py:38-42` | The similarity threshold is applied after the top-3 cut, so a relevant fourth hit is lost when three keyword-heavy hits are below 0.5, and an exact-term first hit below 0.5 is dropped. | AC-3, AC-4 | fix |
| 5 | minor | `ports/chunk_index.py:13-15` | The `similarity` comment says 0 for keyword-only hits, which no adapter does; the 0.0 default lets an adapter that forgets it refuse everything silently. | PY-18 | fix |
| 6 | minor | `services/documents.py:115-119`, `:158-182` | When indexing fails after a partial upsert, the `failed` document keeps its vectors, and restore removes vectors only of deleted documents. | AC-4, AC-5 | fix |
| 7 | minor | `adapters/qdrant_chunk_index.py:72` | `except Exception` turns programming errors into "Qdrant is not reachable". | PY-16 | fix |
| 8 | minor | `services/questions.py:18`, `settings.py:24` | The 0.5 default is defined twice (tests check the services constant, the app uses settings) and `min_similarity` has no 0–1 range check. | GEN-20 | fix |
| 9 | minor | `tests/integration/test_hybrid_search.py`, `tests/contract/test_chunk_index.py` | The AC-3 tests never show that another chunk is semantically closer than the exact-term winner. | TEST-09, AC-3 | fix |
| 10 | minor | `adapters/pinned_models.py:13` | `ParserNotReady` is now raised for the embedding model too; the name no longer fits. | GEN-10 | fix |
| 11 | minor | `Makefile:43`, `:55`, `:108` | `models` and `test-integration` help is out of date, and a taken Qdrant port is not attributed to its owner as the plan says. | GEN-40 | fix |
| 12 | note | `adapters/fakes/chunk_index.py:49-53` | The fake's dense ranking keeps only chunks with similarity > 0, and its last tie-breaker is the id string, unlike `best_first`. | TEST-05 | fix |
| 13 | note | `app.py:79` | Production code imports test fakes only to export the OpenAPI schema. | ADR 0002 | reject: `app.py` is the composition root and the only module allowed to import adapters; `openapi.py` may not (import contract) |
| 14 | note | `adapters/qdrant_chunk_index.py:55`, `:156` | After an embedding model change, the old collection stays on disk forever. | – | reject: kept on purpose, F-09 compares embedding models and reuses their collections; documented in architecture.md |
| 15 | note | `settings.py:22` | `ASSISTANT_QDRANT_URL` accepts any host; chunk text would leave the machine without a guard. | ADR 0004, GEN-41 | backlog (F-10) |
| 16 | note | `ports/embedder.py:14` | `Embedder.dimensions` has no docstring. | PY-18 | fix |
| 17 | note | `plan.md` step 12 | Step 12 has a passing test commit and no green commit; the plan does not say why. | ADR 0009 | fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `5a67077` test, `b18a72f` fix (ingestion jobs carry a generation; every write checks under the lock that the job is current) |
| 2 | `9e4cbc4` test, `27a36c2` fix (search in a worker thread) |
| 3 | `9e4cbc4` test, `27a36c2` fix (restore as a background task at startup) |
| 4 | `11ca797` test, `49c6766` fix (ten candidates, then the threshold, then three; an exact-term hit below it is not cited, recorded for F-04) |
| 5 | `49c6766` (`similarity` required, comment corrected) |
| 6 | `fafecb2` test, `93e7bb1` fix |
| 7 | `fafecb2` test, `93e7bb1` fix |
| 8 | `11ca797` test, `49c6766` fix (one default in Settings, 0 to 1) |
| 9 | `a380dd2` test (the Annex III case shows a closer competitor; the contract case keeps its form, see commit) |
| 10 | `ec50c31` refactor, `86bdc78` test, `42ad837` refactor |
| 11 | `24759fa` build |
| 12 | `deaea26` refactor (`best_first` shared through the port) |
| 13 | rejected: no change |
| 14 | rejected: documented in `architecture.md` in `239a60c` |
| 15 | moved to [backlog follow-ups](../../backlog.md#follow-ups) for F-10 in `4522773` |
| 16 | `12c75a2` refactor |
| 17 | `239a60c` docs (`plan.md`, "Changes during the build") |
