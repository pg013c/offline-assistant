# F-04. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **What the API offers today:**
  - `QuestionService.ask` searches the index (ten candidates, threshold, three passages), then streams an answer from the test model and cites one passage. The ranked list itself is not exposed.
  - Documents can be uploaded and listed, and their status polled; chunks cannot be listed.
  - So the harness needs `POST /api/search` (AC-3) and `GET /api/documents/{id}/chunks`, which resolves expected sources (AC-4).
- **Locations:** chunks carry `article`, `paragraph`, `page` and the heading path, and the Docling parser recognises `Article N` / `Artykuł N`. An expected source "AI Act, Art. 6(1)" can therefore be matched on document and location alone, without hard-coding chunk ids.
- **Isolation already works:** the API takes `ASSISTANT_DATA_DIR`, `ASSISTANT_QDRANT_COLLECTION_PREFIX` and a port, and the E2E journeys use exactly this. Runs start the API in their own process group, so stopping a run never touches other processes.
- **Pinned downloads exist:** `scripts/download_models.py` and `pinned_models.py` show the pattern of download, SHA-256 check and clear message. The corpus follows it.
- **Corpus facts** (downloaded and hashed while writing the ADR):
  - the AI Act is 144 pages per language, about 2.6 MB;
  - the GDPR is 88 pages per language, about 1 MB, available only as PDF/A-1a.
- **Risks:**
  - indexing time: the full English AI Act took 19 s to parse and 17 s to embed (790 chunks; 112 of 113 articles recognised) on the reference Mac, well within NFR-05; step 8 reports it for all four files;
  - the GDPR's article headings may come out differently from the AI Act's;
  - writing 24 correct cases needs care, so every expected source is checked against the indexed corpus before scoring (AC-4).

## Design

### Evaluation project (`evals/`)

Two projects side by side, apart from the backend and the frontend:

- **A uv project** (`evals/pyproject.toml`, Python 3.13): the harness. Dependencies are PyYAML, jsonschema and httpx (ADR 0018). It has its own ruff, mypy and pytest settings, and `make check` runs them.
- **A pnpm project** (`evals/package.json`): Promptfoo `0.124.1` and nothing else.

### Files

- `evals/corpus.json`: the four PDFs with URL, `Accept` header, language, title and SHA-256.
- `evals/datasets/retrieval.yaml`, checked by `evals/datasets/retrieval.schema.json`: one case per entry, with:
  - `id`, `language`, `question`;
  - `expected` (`behaviour`: `answer` or `refuse`; `sources`: a list of `{document, article, paragraph?}`, empty for `refuse`).
- `evals/promptfoo/retrieval.yaml`: the HTTP provider calls `POST {API}/api/search` with `limit: 10`. A JavaScript assertion returns the ranked hits' locations and similarities as metadata, and always passes.

### Python modules (`evals/harness/`)

- `corpus.py`: download, verify and skip-if-present.
- `dataset.py`: load and validate cases.
- `resolve.py`: expected sources to chunk ids, from the chunk listings; unresolved sources are errors.
- `metrics.py`: from per-case ranked hits and expected chunk ids:
  - rank of the first expected chunk;
  - recall@3, recall@10 and MRR, over in-scope cases;
  - out-of-scope cases with no hit at or above the threshold;
  - in-scope cases whose best hit is below the threshold;
  - each metric with its numerator and denominator, and the list of missed cases.
- `gate.py`: compare with a baseline file and name any metric that dropped by more than 5 points.
- `report.py`: a JSON and a Markdown report with metrics, missed cases and run metadata (model pins, Qdrant version, settings, dataset hash, git commit, hardware).
- `run.py`: the orchestration that `make eval` calls:
  1. start the API with the evaluation data directory (`data/eval`), the collection prefix `eval` and port 8021;
  2. upload any corpus file not yet stored and wait until all are ready;
  3. resolve expected sources;
  4. run Promptfoo with telemetry, updates and sharing off;
  5. compute metrics, write the report and apply the gate;
  6. stop the API it started.

### Backend

- `POST /api/search` (`SearchRequest{query: 1–2000 chars, limit: 1–50, default 10}`) returns `SearchHit[]`: `chunk_id`, `document_id`, `document_title`, `location`, `text`, `similarity`.
- `GET /api/documents/{id}/chunks` returns `ChunkSummary[]` (`chunk_id`, `position`, `location`), or `404`.
- Services: `QuestionService.search(query, limit)` returns hits with document titles and skips no hit; the threshold is the harness's business. `DocumentService.chunks(id)` returns the stored chunks.

### Make targets

- `make eval-corpus`.
- `make eval`: needs `make models`, `make qdrant` and `make eval-corpus`.
- `make check-evals`: ruff, mypy and pytest for `evals/`, run by `make check` and by CI's Backend job.

## Steps

### Step 1. Evaluation projects, corpus download and targets

- Kind: setup (one `build` commit)
- Change:
  - `evals/pyproject.toml` and `evals/uv.lock`;
  - `evals/package.json` with Promptfoo and its lockfile;
  - `evals/corpus.json`;
  - `make eval-corpus` with `evals/harness/corpus.py` (downloads and verifies; no tests, like `download_models.py`);
  - `make check-evals`, empty but wired;
  - `make setup` installs both projects, and `.gitignore` covers `data/eval/`;
  - README licences and setup;
  - CI Backend job runs `make check-evals`.
- Done when: `make eval-corpus` fetches and verifies four files, and a second run reports them present without downloading.
- [x] green

### Step 2. Search endpoint

- Kind: code
- Tests first:
  - `test_question_service.py`: search returns hits best first with document titles, similarities and locations, honours the limit, and returns low-similarity hits too.
  - `test_search_api.py`:
    - `200` with the hit fields;
    - the limit is respected;
    - an empty or too long query, and a limit out of range, give `422` with the standard body.
- Change: `services/questions.py`, `api/routes/search.py`, `api/schemas.py`, `app.py`, `make api-client`.
- [x] red
- [x] green

### Step 3. Chunk listing

- Kind: code
- Tests first:
  - `test_document_service.py`: the stored chunks of a document, or `DocumentNotFound`;
  - `test_documents_api.py`: `GET /api/documents/{id}/chunks` lists ids, positions and locations; an unknown id gives `404`.
- Change: `services/documents.py`, `api/routes/documents.py`, `make api-client`.
- [ ] red
- [ ] green

### Step 4. Retrieval dataset

- Kind: eval (its own commit, TEST-22)
- Cases first: `evals/datasets/retrieval.yaml` with the 24 cases of the spec table and its schema.
- Tests: `evals/tests/test_dataset.py`:
  - every case validates;
  - ids are unique;
  - both languages appear;
  - at least three cases are out of scope, and they expect `refuse` with no sources.
- Done when: the cases are reviewed against the corpus text; step 7 also checks that every source resolves.
- [ ] red
- [ ] green

### Step 5. Metrics and regression gate

- Kind: code
- Tests first, in `evals/tests/test_metrics.py` and `test_gate.py`:
  - the rank of the first expected chunk;
  - recall@k and MRR over in-scope cases only;
  - the out-of-scope and in-scope refusal shares at the threshold;
  - counts and missed cases;
  - a baseline drop of more than 5 points names the metric and fails;
  - a drop of 5 points or less passes;
  - a missing baseline passes and says it sets one.
- Change: `evals/harness/metrics.py`, `gate.py`.
- [ ] red
- [ ] green

### Step 6. Source resolution and reports

- Kind: code
- Tests first, in `evals/tests/test_resolve.py` and `test_report.py`:
  - expected sources resolve to the chunk ids whose document and location match;
  - a paragraph-less source matches every paragraph of the article;
  - an unresolved source names the case and the source;
  - the report holds metrics with counts, missed cases and the metadata fields of AI-61;
  - the Markdown table lists every metric.
- Change: `evals/harness/resolve.py`, `report.py`.
- [ ] red
- [ ] green

### Step 7. Run orchestration and Promptfoo

- Kind: infra
- Tests first: `evals/tests/test_run.py` (marker `integration`) runs the harness end to end on the two F-02 excerpts with a three-case fixture dataset. It checks that:
  - the API it starts is stopped;
  - the development collection is untouched;
  - the report has every metric;
  - Promptfoo ran with telemetry, updates and sharing disabled.
- Change: `evals/harness/run.py`, `evals/promptfoo/retrieval.yaml` and its assertion script, `make eval`.
- [ ] red
- [ ] green

### Step 8. Baseline

- Kind: eval
- Run `make eval` on the full corpus.
- Commit the record in `docs/evals/2026-10-29-retrieval-baseline.md` and the gate's baseline in `docs/evals/retrieval-baseline.json`, with the ingestion time against NFR-05.
- Cases that miss are analysed (`eval-analyst`) and reported, not edited away (TEST-22).
- [ ] green

### Step 9. Documentation

- Kind: setup (one `docs` commit)
- Change:
  - `docs/architecture.md` (evaluation flow, new endpoints);
  - `docs/standards/testing.md` (`make eval`, `make check-evals`);
  - README (how to run an evaluation, the baseline result);
  - backlog.
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 corpus download, verified, not repeated | 1 |
| AC-2 isolated indexing through the API | 7 |
| AC-3 search endpoint | 2 |
| AC-4 dataset schema and resolved sources | 3, 4, 6, 7 |
| AC-5 metrics with counts and missed cases | 5, 7, 8 |
| AC-6 run metadata and committed baseline | 6, 8 |
| AC-7 regression gate | 5, 8 |
| AC-8 offline, no telemetry | 1, 7 |
