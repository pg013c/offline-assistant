# F-04a. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **Both indexes embed and search `chunk.text` only:**
  - `QdrantChunkIndex.add` (`qdrant_chunk_index.py:76, 82`);
  - `InMemoryChunkIndex.add` (`fakes/chunk_index.py:34, 36`).

  The payload keeps the chunk text, location and heading path, and search rebuilds `Chunk` from it. Changing what is indexed therefore leaves what is returned and cited untouched.
- **The chunker can already turn content into heading text:**
  - `_Chunker` keeps a heading path and an `_expecting_title` flag, so the heading right after "Article 6" is appended as the article's title (`domain/documents.py:144-165`);
  - every content block clears the flag.

  The section-title rule extends this: after any heading, a title-like paragraph is appended to the path instead of starting a chunk.
- **Stored chunks are the source of truth:**
  - `restore()` indexes ready documents from them without parsing, and parses again only documents with no chunks;
  - `Document` has no record of which chunker cut its chunks, so a chunking change would otherwise keep the old chunks forever (AC-3).
- **Collections** are named `<prefix>-<model>-v<SCHEMA_VERSION>` (`qdrant_chunk_index.py:21, 45`). Raising the version gives a fresh collection that `restore()` fills; the old one stays, as decided in F-03 review finding 14.
- **Pinned ids:** the F-02 snapshot pins positions for the AI Act excerpts (pages 53–54). In those excerpts the section titles are parsed as headings already, so the snapshot may not change. Step 4 checks this either way.
- **Evaluation:**
  - the "before" numbers are the F-04 baseline in `docs/evals/` (dataset version 2, the code on `main`);
  - `make eval` starts from an empty index, so the "after" run measures this branch.
- **Risks:**
  - the context prefix raises similarities across the board, which may lift an out-of-scope question over 0.5 (spec decision 4);
  - a too-broad title rule could swallow real one-line paragraphs, which is why the rule is narrow and has negative tests.

## Design

### Domain

- `CHUNKER_VERSION = 2` and `indexed_text(chunk) -> str`: the heading path joined with " > ", a blank line, then the text. A chunk with no heading path is indexed as its text alone.
- `Document` gains `chunker_version: int | None`, `None` for documents ready before this feature.
- `_Chunker`: right after a heading, a `paragraph` that is the first block under it, has at most 200 characters and does not end with `.;:,?!)` is appended to the heading path one level deeper. Any other block clears the expectation.

### Services

- `ingest` records `CHUNKER_VERSION` on the document when it becomes ready.
- `restore()` treats a ready document whose `chunker_version` differs as needing parsing: it drops the document's vectors, sets it to `processing` and queues it.

### Adapters

- Both indexes embed and BM25-index `indexed_text(chunk)`.
- `SCHEMA_VERSION = 2`.
- The payload, and so what search returns, is unchanged.

## Steps

### Step 1. Indexed text

- Kind: code
- Tests first, in `tests/unit/domain/test_indexed_text.py`:
  - the context is the heading path joined with " > " and comes before the text, separated by a blank line;
  - with no heading path, the indexed text is the text;
  - the chunk's own text is not changed.
- Change: `domain/documents.py`.
- [x] red
- [x] green

### Step 2. Section titles join the heading path

- Kind: code
- Tests first, in `test_structured_chunking.py`:
  - a short title-like paragraph right after a heading joins the path and is not a chunk, and the following content carries the longer path;
  - a paragraph ending with a full stop, a colon or a comma stays a chunk;
  - one longer than 200 characters stays a chunk;
  - one after other content under the heading stays a chunk;
  - the article title rule is unchanged.
- Change: `domain/documents.py` (chunker, `CHUNKER_VERSION = 2`).
- [x] red
- [x] green

### Step 3. Re-parse documents chunked by an older chunker

- Kind: code
- Tests first:
  - store contract: `chunker_version` survives `update` and reloading, and metadata without it loads as `None`;
  - `test_document_service.py`:
    - ingestion records the current chunker version;
    - restore requeues a ready document with an older or missing version, drops its vectors, and after ingestion it is ready with the current version;
    - a document with the current version is not parsed again.
- Change: `domain/documents.py` (`Document`), `adapters/file_document_store.py`, `adapters/fakes/document_store.py`, `services/documents.py`.
- [x] red
- [ ] green

### Step 4. Both indexes use the indexed text; schema version 2

- Kind: code
- Tests first:
  - chunk index contract (in memory and Qdrant): a chunk whose article title, not its text, matches the question ranks first, and search returns its text without the context;
  - `test_qdrant_chunk_index.py`: the collection name ends in `-v2`;
  - the F-02 snapshot (`test_docling_parser.py`) is re-checked, and updated in a commit of its own if the new chunking moves any id (AC-6).
- Change: `adapters/qdrant_chunk_index.py`, `adapters/fakes/chunk_index.py`.
- [ ] red
- [ ] green

### Step 5. Measure and record

- Kind: eval
- Run `make eval` on this branch.
- Compare with the F-04 baseline:
  - check AC-4 and AC-5;
  - check the out-of-scope similarities against the 0.5 threshold.
- Commit the record `docs/evals/2026-10-29-retrieval-article-context.md` (before and after, per-case changes, analysis of what still misses) and the new `retrieval-baseline.json`.
- If a criterion fails, stop and bring the numbers to the human before changing anything else.
- [ ] green

### Step 6. Documentation

- Kind: setup (one `docs` commit)
- Change:
  - `docs/architecture.md` (what is indexed, chunker version and re-parsing, schema version 2);
  - README status and numbers;
  - backlog.
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 indexed text has the context, cited text does not | 1, 4 |
| AC-2 section titles join the heading path | 2 |
| AC-3 documents of an older chunker are parsed again | 3, 4 |
| AC-4 exact references found in the top 10 | 5 |
| AC-5 metrics against the baseline, recorded | 5 |
| AC-6 pinned ids change only where needed | 4 |
