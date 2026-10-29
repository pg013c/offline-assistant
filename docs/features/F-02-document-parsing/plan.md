# F-02. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- Ingestion today is synchronous: `DocumentService.upload` checks extension (`.txt`, `.md`), size (5 MB) and UTF-8, splits text at blank lines (`domain.split_into_chunks`), saves `<id>.txt` + `<id>.json` and indexes. `restore()` re-splits every stored text at startup. Document id is the SHA-256 of the decoded text; chunk id is `"{document_id}:{position}"`.
- `Document` has no status, page count or location; `Chunk` has no location; `Citation` has chunk id, document id and title, quote. The citation event mirrors it. The UI shows the document title in the citation list and dialog.
- Route tests (`tests/unit/api/`) build the real composition root with a temporary data directory (F-01 review #16, planned for F-03). With Docling wired in, these tests would import PyTorch and need models. A test-only parser chosen by settings, like `ASSISTANT_CHAT_MODEL`, keeps them fast.
- Docling (ADR 0015) returns a `DoclingDocument` with items in reading order, each with a label (section header, text, list item, table, page header/footer) and provenance (page number). It takes `artifacts_path`, OCR options (Tesseract CLI, languages) and a page limit. Its import is slow (PyTorch); only the adapter imports it, lazily.
- EUR-Lex shows "Article 6" and its title as separate headers, and numbered paragraphs as text items starting with `1.`; points `(a)`, `(b)` are list items. Polish: "Artykuł 6". Page headers and footers (journal reference, page number) must be dropped, or chunks pick them up.
- Risks: Docling output changes between versions (pinned; fixtures guard ids); OCR of a scan may mis-number paragraphs (the scan fixture asserts article and page only); Tesseract is not yet installed on the reference Mac.

## Design

**Domain**

- `ParsedDocument(page_count, blocks)`; `Block(kind: heading | paragraph | list_item | table, text, page: int | None, level: int | None)`: our own structure, independent of Docling.
- `ChunkLocation(heading_path: tuple[str, ...], article: str | None, paragraph: str | None, page: int | None)`. `Chunk` gains `location`. `Citation` gains `location`.
- `chunk_document(document_id, parsed, max_chars=2000) -> list[Chunk]`: walks blocks keeping a heading path; recognises `Article N` / `Artykuł N` headings and numbered paragraphs (`N.`) in both languages; list items join the paragraph they belong to; a new article or heading starts a new chunk; a part longer than `max_chars` splits at sentence boundaries; a table is one chunk. Chunk id stays `"{document_id}:{position}"`, position in this deterministic order.
- `Document` gains `status: processing | ready | failed`, `page_count: int | None`, `failure_reason: str | None`. Document id is the SHA-256 of the uploaded bytes (for UTF-8 text this equals today's id).
- Errors: `DocumentUnreadable(reason)` from parsing; `UnsupportedFileType`, `FileTooLarge` stay. `NotUtf8Text` becomes a parse failure of the text parser.

**Ports**

- `DocumentParser.parse(filename, content: bytes) -> ParsedDocument`, raises `DocumentUnreadable`.
- `DocumentStore`: `save_upload(document, content: bytes)`, `update(document)`, `save_chunks(document_id, chunks)`, `load_chunks(document_id)`, `load_original(document_id)`, `get`, `list_documents`. Files: `<id>.<ext>` (original), `<id>.json` (metadata), `<id>.chunks.json`.
- `IngestionQueue.submit(document_id)`: runs ingestion later. Adapters: `ThreadIngestionQueue` (one worker thread, so only one parse holds memory at a time), fake `InlineIngestionQueue` (runs at once, for tests).

**Adapters**: `TextDocumentParser` (`.txt`, `.md`: blank-line paragraphs, `#` headings, UTF-8 or `DocumentUnreadable`); `DoclingDocumentParser` (PDF, DOCX, PNG, JPG; Tesseract `eng+pol`; drops page headers and footers; 500-page limit; `ensure_ready()` checks the model manifest and `tesseract --list-langs`); `RoutingDocumentParser` picks by extension; `fakes/FakeDocumentParser` returns a given `ParsedDocument`.

**Services**: `DocumentService.upload(filename, content)`: checks type and 50 MB, returns the existing document for known bytes, else stores the original with status `processing` and submits it. `ingest(document_id)`: parse, chunk, save chunks, index, status `ready` with counts; any `DocumentUnreadable` → `failed` with the reason. `restore()`: indexes stored chunks of `ready` documents and resubmits `processing` ones. `QuestionService` puts the chunk location on the citation.

**Settings**: `ASSISTANT_MODELS_DIR` (required when the parser is `docling`), `ASSISTANT_DOCUMENT_PARSER: docling | text-only` (default `docling`; `text-only` for route tests). Startup fails per AC-7 when the Docling parser is not ready.

**API**: `POST /api/documents` → `202 DocumentResponse` (adds `status`, `page_count`, `failure_reason`); limit 50 MB; accepted types extended. `ChatCitationEvent` gains `location: CitationLocation {heading_path, article, paragraph, page}`. `make api-client`.

**UI**: the document panel accepts the new types, shows status (processing, ready with counts, failed with reason) and refetches every 2 s while any document is processing. Citations show a location label: `Art. 6(2), p. 53`; without an article, the last heading and page; built by one formatting function.

**Tooling**: `make models` (`docling-tools models download layout tableformer` into `ASSISTANT_MODELS_DIR/docling` plus a SHA-256 manifest), `make test-integration` (pytest `-m integration`; `make check` keeps excluding them, as it excludes `make e2e`). CI: new job `Integration`; the `Integration` and `E2E` jobs install Tesseract and restore models from a cache keyed on `uv.lock`.

**Fixtures** (`backend/tests/fixtures/documents/`): EU AI Act Articles 5–6 in English and Polish as PDF pages cut from the EUR-Lex PDFs, a scan (pages rendered to an image with noise, saved as image-only PDF), a photo-like PNG, a generated DOCX with headings and a table, a password-protected PDF, a corrupt PDF, a PDF without text. A script `backend/tests/fixtures/make_documents.py` produces them; its source and the EUR-Lex URLs are committed, so they can be rebuilt.

## Steps

### Step 1. Dependencies, model fetching and settings

- Kind: setup (one `build` commit)
- Change: `uv add docling-slim[format-pdf,format-docx,models-local]` (ADR 0015); `make models`, `make test-integration`; `ASSISTANT_MODELS_DIR` and `ASSISTANT_DOCUMENT_PARSER` in `.env.example`; `pytest` default `-m "not integration"`; README setup lists Tesseract.
- Done when: `make models` fills the directory and writes the manifest; `make check` is green.
- [x] green

### Step 2. Chunking along headings, paragraphs and tables

- Kind: code
- Tests first: `tests/unit/domain/test_structured_chunking.py`: one chunk per paragraph under a heading, with the heading path and page; a new heading starts a new chunk; a long paragraph splits at sentence boundaries within `max_chars`; a table stays one chunk however long; ids are `"{doc}:{n}"` and repeatable.
- Change: `domain/documents.py` (`ParsedDocument`, `Block`, `ChunkLocation`, `chunk_document`).
- [x] red
- [x] green

### Step 3. Articles and numbered paragraphs in English and Polish

- Kind: code
- Tests first: same file: `Article 6` and `Artykuł 6` set the article; `1.`, `2.` set the paragraph and start a chunk; points `(a)` join their paragraph; no chunk holds text from two articles; an article without numbered paragraphs is one chunk (or split by size).
- Change: `domain/documents.py`.
- [x] red
- [x] green

### Step 4. Parser port, text parser and fake

- Kind: code
- Tests first: `tests/contract/test_document_parser.py` (text parser and fake): returns blocks in order with a page count; `tests/unit/adapters/test_text_document_parser.py`: `#` lines are headings, blank lines separate paragraphs, invalid UTF-8 raises `DocumentUnreadable`.
- Change: `ports/document_parser.py`, `adapters/text_document_parser.py`, `adapters/fakes/document_parser.py`, `domain/errors.py`.
- [x] red
- [x] green

### Step 5. Store originals, status and chunks

- Kind: code
- Tests first: `tests/contract/test_document_store.py` extended (file store and fake): an upload is stored with status `processing` and its original bytes; `update` changes status and counts; saved chunks load back equal, including locations; `list_documents` and `get` read metadata only.
- Change: `ports/document_store.py`, `adapters/file_document_store.py`, `adapters/fakes/document_store.py`, `domain/documents.py` (`Document` fields).
- [x] red
- [x] green

### Step 6. Ingestion in the background

- Kind: code
- Tests first: `tests/unit/services/test_document_service.py` rewritten with the fake parser and `InlineIngestionQueue`: upload returns `processing` and submits; after ingestion the document is `ready` with chunk and page counts and searchable; a `DocumentUnreadable` gives `failed` with the reason and nothing indexed; files over 50 MB and unknown types are rejected; the same bytes return the same document; `restore` indexes stored chunks of ready documents without parsing and resubmits processing ones; `tests/unit/adapters/test_thread_ingestion_queue.py`: jobs run one at a time, in order.
- Change: `services/documents.py`, `ports/ingestion_queue.py`, `adapters/thread_ingestion_queue.py`, `adapters/fakes/ingestion_queue.py`.
- [x] red
- [x] green

### Step 7. Citations carry the chunk location

- Kind: code
- Tests first: `tests/unit/services/test_question_service.py`: the citation has the cited chunk's location.
- Change: `domain/answers.py`, `services/questions.py`.
- [x] red
- [x] green

### Step 8. Docling parser and fixtures

- Kind: code
- Tests first: `tests/integration/test_docling_parser.py` (marker `integration`) on the fixtures: the English and Polish excerpts give `Article 6` and paragraphs `1.`, `2.` with their pages and no page headers or footers; DOCX gives headings and a table; the scan and the photo give text from the right article and page; parsing the same file twice gives identical chunks; password-protected, corrupt, text-free and over-limit files raise `DocumentUnreadable` with a reason; `ensure_ready` names the missing model or language and `make models`.
- Change: `adapters/docling_parser.py`, `adapters/routing_parser.py`, fixtures and `make_documents.py`; CI job `Integration` (Tesseract, model cache, `make models`, `make test-integration`).
- [x] red
- [x] green

### Step 9. API: accepted uploads, status and citation location

- Kind: code
- Tests first: `tests/unit/api/test_documents_api.py` with `ASSISTANT_DOCUMENT_PARSER=text-only`: upload returns `202` with `processing`, and the list shows `ready` with counts once ingested; `413`, `415`, `422` keep the standard body; `test_chat_api.py`: the citation event carries `location`; `test_settings.py` / app tests: with the Docling parser and an empty models directory, startup fails naming the model and `make models`.
- Change: `api/schemas.py`, `api/routes/documents.py`, `api/errors.py`, `settings.py`, `app.py` (queue lifecycle in lifespan); `make api-client`.
- [x] red
- [x] green

### Step 10. Document panel with status

- Kind: ui
- Tests first: `DocumentPanel.test.tsx`: the input accepts PDF, DOCX, PNG, JPG, TXT, MD; a processing document shows "Processing…" and the list refetches until it is ready; a ready one shows passages and pages; a failed one shows the reason.
- Change: `features/documents/DocumentPanel.tsx`, `useDocuments.ts`.
- [x] red
- [x] green

### Step 11. Citation location in the chat

- Kind: ui
- Tests first: `features/chat/citationLabel.test.ts`: `Art. 6(2), p. 53`, `Art. 6, p. 53`, a heading with a page, a page only, nothing; `ChatView.test.tsx`: the citation list and the dialog show the label next to the title.
- Change: `features/chat/citationLabel.ts`, `ChatView.tsx`, `CitationDialog.tsx`, `useChatStream.ts` types.
- [x] red
- [x] green

### Step 12. Journey with a PDF

- Kind: ui
- Tests first: `frontend/e2e/ask-question.spec.ts`: upload the English AI Act excerpt PDF, wait for "ready", ask about high-risk classification, open the citation and see `Art. 6` and a page.
- Change: Playwright starts the API with the Docling parser and `ASSISTANT_MODELS_DIR`; CI job `E2E` installs Tesseract and restores the model cache.
- [ ] red
- [ ] green

### Step 13. Documentation

- Kind: setup (one `docs` commit)
- Change: `docs/architecture.md` (parser port and adapters, ingestion flow, data model), `docs/standards/testing.md` (integration tests run with `make test-integration` and in CI job `Integration`), README (setup, `make models`, licence list), backlog.
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 upload of each format, `202`, ready and searchable | 6, 8, 9, 10 |
| AC-2 article and paragraph chunks in EN and PL with pages | 3, 8 |
| AC-3 no chunk across articles, size bound, tables whole | 2, 3 |
| AC-4 same ids after re-ingestion and restart | 2, 5, 6, 8 |
| AC-5 unreadable files fail with a reason; upload rejections | 4, 6, 8, 9, 10 |
| AC-6 location in the citation event, client and UI | 7, 9, 11 |
| AC-7 missing model fails at startup, no download | 1, 8, 9 |
| AC-8 PDF journey shows article and page | 12 |
