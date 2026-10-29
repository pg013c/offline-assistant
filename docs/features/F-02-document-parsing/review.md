# F-02. Review

- Reviewed range: `main...feat/F-02-document-parsing` at `f61f5a5`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: not applicable (retrieval and the model do not change; evaluations start with F-04)
- Checks: `make check` (4 import contracts, 137 backend tests, 37 UI tests, API contract), `make test-integration` (17) and `make e2e` pass. Red commits precede green ones; green commits touch no test paths.
- Verification: all 17 findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `backend/scripts/download_models.py:43-51`, `adapters/docling_parser.py:61-63` | The layout model is fetched at Docling's `revision="main"`, and `ensure_ready` checks only that manifest files exist, not their hashes. Another machine or a CI cache miss can get different weights, different blocks and different chunk ids for the same file. | AI-40, GEN-31, ADR 0015, AC-4 | fix |
| 2 | major | `domain/documents.py:23`, `adapters/file_document_store.py:73-74`, `services/documents.py:117-121` | F-01 metadata has no `status`, so it loads as `ready` with no stored chunks: listed but never found, and re-uploading returns the same broken record. | AC-4 | fix |
| 3 | minor | `services/documents.py:97-105` | Only parsing is guarded; a failure while chunking, saving or indexing leaves the document `processing` forever, and the UI keeps polling. | AC-5, GEN-21 | fix |
| 4 | minor | `services/documents.py:65-68` | A `failed` document can never be retried: uploading the same bytes returns the failed record. | AC-5 | fix |
| 5 | minor | `services/documents.py:65-78`, `adapters/file_document_store.py:23-29, 66-70` | Two simultaneous uploads of the same file race: both may queue ingestion (duplicate chunks in the index) or one may fail on the shared `.partial` file. | PY-14 | fix |
| 6 | minor | `adapters/thread_ingestion_queue.py:21-24`, `app.py:54, 63` | Shutdown waits for every queued parse, although restore requeues unfinished documents; the queue also starts in `create_app`, not in the lifespan. | – | fix |
| 7 | minor | `app.py:37` | `or settings.models_dir is None` is dead code that would silently fall back to text-only instead of failing. | GEN-05, GEN-20 | fix |
| 8 | minor | `.env.example:7-8` | `ASSISTANT_MODELS_DIR` is described as optional with a default; only `make` supplies the default, and the app requires it with the Docling parser. | GEN-20, GEN-40 | fix |
| 9 | minor | `adapters/docling_parser.py:17`, `backend/pyproject.toml:8-16` | `pypdfium2` is imported but not declared; `torch`, `torchvision`, `opencv-python-headless`, `pypdfium2` and the `convert-core` extra are not recorded in ADR 0015, and `torchvision` and `pypdfium2` are missing from the README licence table. | GEN-30, NFR-07 | fix |
| 10 | minor | `adapters/docling_parser.py:187-191` | Every list item with an `N.` marker becomes a paragraph, so an ordinary numbered list in a Word file splits into one chunk per item. | plan step 3 | fix |
| 11 | minor | `domain/documents.py:197, 202` | A single word longer than `max_chars` (URL, base64, OCR noise) is kept whole, so a non-table chunk can exceed the limit. | AC-3 | fix |
| 12 | minor | `tests/unit/test_settings.py:55, 76, 87` | `main()` sets the Hugging Face offline variables in `os.environ`, and `delenv` on an absent variable records nothing to restore, so they leak into later tests; each `main()` also starts a queue thread that is never closed. | TEST-06 | fix |
| 13 | note | `domain/documents.py:185-187` | All parts of a chunk split by size carry the page where it starts, even after a page break. | AC-2 | fix |
| 14 | note | `domain/errors.py:9` | `UnsupportedFileType` docstring still says only text and Markdown are accepted. | – | fix |
| 15 | note | `tests/integration/test_docling_parser.py:122-123` | No committed snapshot of chunk ids and locations for the fixtures, so a Docling upgrade that shifts positions passes unnoticed (ADR 0015 relies on such tests). | ADR 0015, AC-4 | fix |
| 16 | note | `tests/fixtures/make_documents.py:11` | The fixture script uses an unpinned `pikepdf` (MPL-2.0) through `uv run --with`. | GEN-30 | fix |
| 17 | note | `services/documents.py:58-63` | Deviation from the plan: invalid UTF-8 text stays an upload-time `422` instead of a parse failure; not recorded in `plan.md`. | – | fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
