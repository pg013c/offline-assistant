# F-01. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- Backend today: `create_app(settings)` with the health route, `main()` factory, `Settings` with `data_dir`, structlog setup, empty `domain`, `ports`, `services`, `adapters/fakes`. Four import contracts guard the layers; services may not import FastAPI or settings.
- Frontend today: app shell with `ApiStatus`, generated client in `src/api/`, TanStack Query, shared msw server and `renderWithQueryClient` in `src/test/`. No routing, no forms yet.
- FastAPI 0.162 supports SSE natively (`fastapi.sse.EventSourceResponse`, any HTTP method) and documents the event model as `itemSchema` of `text/event-stream`. Whether `openapi-typescript` 7 emits types for `itemSchema` is unverified; the event model is a named component, so its type is generated either way (`components["schemas"]`). Checked in step 8.
- Uploads need `python-multipart`; the UI needs an SSE parser for `POST` streams; the journey needs Playwright. All three are in [ADR 0013](../../adr/0013-upload-streaming-and-e2e-dependencies.md), accepted with this plan.
- `frontend/e2e/*` and `scripts/ci/test-*` are already test paths for the hook and the commit check.

## Design

**Domain** (`domain/`): `Document` (id, title, filename, chunk count), `Chunk` (id, document id, position, text), `Citation` (chunk id, document id, document title, quote), answer events `AnswerText(text)`, `AnswerCitation(citation)`, `AnswerEnd(model_id, found: bool)`. `split_into_chunks(document_id, text)` splits on blank lines. Document id = first 16 hex characters of the SHA-256 of the content (AC-3); chunk id = `"{document_id}:{position}"`.

**Ports** (`ports/`):

- `DocumentStore`: `save(document, content)`, `list()`, `load_all() -> list[(Document, str)]`.
- `ChunkIndex`: `add(chunks)`, `search(query, limit) -> list[ScoredChunk]`. F-03 replaces the keyword adapter with embeddings and Qdrant and decides whether the port splits into `Embedder` + `VectorStore` as in the architecture.
- `ChatModel`: `model_id`, `stream_answer(question, passages) -> AsyncIterator[str]`. F-06 revisits the signature for tool calling.

**Adapters**: `LocalFileDocumentStore` (`data_dir/documents/<id>.txt` + `<id>.json`), `KeywordChunkIndex` (in memory, lower-cased words, small English stop-word list), `fakes/FakeDocumentStore`, `fakes/FakeExtractiveChatModel` (`model_id = "fake-extractive"`; streams the first two sentences of the first passage word by word). The fake chat model is wired in production until F-06, selected by `ASSISTANT_CHAT_MODEL=fake-extractive` (the only allowed value for now).

**Services**: `DocumentService.upload(filename, content)` validates extension, size (5 MB) and UTF-8, raising domain errors; returns the existing document for known content; indexes chunks. `list()`, `restore()` (load all stored documents into the index at startup). `QuestionService.ask(question) -> AsyncIterator[AnswerEvent]`: search; no hit → one `AnswerText` saying no relevant passage was found and `AnswerEnd(found=False)`; otherwise model text, then one citation per passage used (the quote is the passage's first sentences, taken from the chunk text), then `AnswerEnd(found=True)`.

**API**: `POST /api/documents` (multipart, `201 DocumentResponse`), `GET /api/documents`, `POST /api/chat` (`{question}` → `EventSourceResponse` of `ChatEvent`, a discriminated union on `type`: `text`, `citation`, `end`). Domain errors map to `415`, `413`, `422` with `ErrorResponse {code, message, details}` in one exception handler module (PY-22). Services reach routes through `Depends` functions that read them from `app.state`, set by the composition root; a lifespan handler calls `restore()`.

**UI**: `features/documents` (`useDocuments`, `useUploadDocument`, `DocumentPanel` with a labelled file input and the list), `features/chat` (`useChatStream`: `POST` via the generated client with `parseAs: "stream"`, `eventsource-parser`, typed events, states idle/streaming/done/error; `ChatView` with the question form, streamed answer, model label and citation list; `CitationDialog` on a native `<dialog>`). `App` lays out the two panels.

**E2E**: `frontend/playwright.config.ts` starts the API (temporary data dir, `API_PORT`) and Vite through `webServer`; one journey with a hand-written fixture document. `make e2e`; CI job `E2E` installs Chromium.

## Steps

### Step 1. Document identity and chunking

- Kind: code
- Tests first: `backend/tests/unit/domain/test_chunking.py`: blank lines split chunks; surrounding whitespace trimmed; empty pieces dropped; chunk ids `"{doc}:{n}"`; same content gives the same document id; different content gives a different id; title is the filename without extension.
- Change: `domain/documents.py`.
- [x] red
- [x] green

### Step 2. Keyword chunk index

- Kind: code
- Tests first: `backend/tests/contract/test_chunk_index.py` run against `KeywordChunkIndex`: ranks by number of shared words; ignores case and stop words; respects `limit`; returns nothing when no word is shared or the index is empty.
- Change: `ports/chunk_index.py`, `adapters/keyword_index.py`.
- [x] red
- [x] green

### Step 3. Fake extractive chat model

- Kind: code
- Tests first: `backend/tests/contract/test_chat_model.py` against `FakeExtractiveChatModel`: reports `fake-extractive`; streams several pieces whose concatenation is the first two sentences of the first passage; same input gives the same output.
- Change: `ports/chat_model.py`, `adapters/fakes/chat_model.py`.
- [ ] red
- [ ] green

### Step 4. Document store

- Kind: code
- Tests first: `backend/tests/contract/test_document_store.py` run against `FakeDocumentStore` and `LocalFileDocumentStore` (in `tmp_path`): saved documents are listed and loaded with their text; saving the same document twice keeps one; `LocalFileDocumentStore` writes only under `data_dir/documents` and a new instance on the same directory sees earlier documents.
- Change: `ports/document_store.py`, `adapters/fakes/document_store.py`, `adapters/file_document_store.py`.
- [ ] red
- [ ] green

### Step 5. Document service

- Kind: code
- Tests first: `backend/tests/unit/services/test_document_service.py` with fakes: upload stores and indexes; rejects other extensions, more than 5 MB and invalid UTF-8 with distinct domain errors and stores nothing; duplicate content returns the existing document; `restore()` indexes stored documents.
- Change: `domain/errors.py`, `services/documents.py`.
- [ ] red
- [ ] green

### Step 6. Question service

- Kind: code
- Tests first: `backend/tests/unit/services/test_question_service.py` with fakes: events come as text, then citations, then end; each citation's quote is a substring of its chunk; no documents or no shared word gives one "no relevant passage" text, no citation and `found=False`; the end event carries the model id.
- Change: `domain/answers.py`, `services/questions.py`.
- [ ] red
- [ ] green

### Step 7. Document endpoints and wiring

- Kind: code
- Tests first: `backend/tests/unit/api/test_documents_api.py`: upload returns `201` with id, title and chunk count and the document is listed; `415`, `413`, `422` return the standard error body and nothing is listed; uploading the same content twice returns the same id; a second app on the same data directory lists earlier documents (restart, AC-9).
- Change: `api/schemas.py`, `api/errors.py`, `api/dependencies.py`, `api/routes/documents.py`, `app.py` (wiring, lifespan), `settings.py` (`chat_model`), `pyproject.toml` (`python-multipart`), regenerated client.
- [ ] red
- [ ] green

### Step 8. Chat endpoint over SSE

- Kind: code
- Tests first: `backend/tests/unit/api/test_chat_api.py`: after an upload, `POST /api/chat` returns `text/event-stream` whose events parse into `text`…, `citation`…, `end` in that order; with no documents the stream has no citation; the OpenAPI schema documents `text/event-stream` and has `ChatEvent` and its variants in `components`.
- Change: `api/schemas.py`, `api/routes/chat.py`, `app.py`, regenerated client (check that `ChatEvent` types are generated).
- [ ] red
- [ ] green

### Step 9. Document panel

- Kind: ui
- Tests first: `frontend/src/features/documents/DocumentPanel.test.tsx` with msw: lists documents; uploading through the labelled file input adds the new document; a rejected upload shows the API's error message.
- Change: `useDocuments.ts`, `useUploadDocument.ts`, `DocumentPanel.tsx`.
- [ ] red
- [ ] green

### Step 10. Chat stream hook

- Kind: ui
- Tests first: `frontend/src/features/chat/useChatStream.test.tsx` with msw streaming an SSE body: text pieces accumulate in order; citations are collected; the end event sets the model and `done`; a failed request sets `error`; a new question resets the previous answer.
- Change: `useChatStream.ts`, `frontend/package.json` (`eventsource-parser`).
- [ ] red
- [ ] green

### Step 11. Chat view and citations

- Kind: ui
- Tests first: `frontend/src/features/chat/ChatView.test.tsx` and an updated `App.test.tsx`: submitting the form streams the answer into the page; the model label is shown (`fake-extractive`); each citation is a button; opening it shows the quote and document title in a dialog; the "no relevant passage" answer shows no citations; `App` shows both panels.
- Change: `ChatView.tsx`, `CitationDialog.tsx`, `App.tsx`.
- [ ] red
- [ ] green

### Step 12. End-to-end journey

- Kind: setup
- Change: `@playwright/test`, `frontend/playwright.config.ts`, `frontend/e2e/ask-question.spec.ts` (upload the fixture, ask, see the streamed answer and the model label, open a citation), `frontend/e2e/fixtures/sample-policy.txt`, Makefile `e2e` and Chromium install in `setup`, CI job `E2E`, README.
- Done when: `make e2e` passes locally and the journey fails if the citation button is removed from `ChatView` (checked by hand, noted here).
- Commit: `build(e2e): run the first browser journey in CI`
- [ ] done

### Step 13. Documentation

- Kind: setup
- Change: `docs/architecture.md` (ports `DocumentStore`, `ChunkIndex`, `ChatModel` and the F-01 adapters), README (what works now), `.env.example` (`ASSISTANT_CHAT_MODEL`).
- Commit: `docs(F-01): document the walking skeleton`
- [ ] done

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 upload, store, list | 4, 5, 7, 9 |
| AC-2 rejected uploads | 5, 7, 9 |
| AC-3 no duplicates, stable ids | 1, 4, 5, 7 |
| AC-4 text, citations, end; quotes verbatim | 6, 8 |
| AC-5 no relevant passage | 2, 6, 8, 11 |
| AC-6 event types in schema and client | 8 |
| AC-7 UI upload, streamed answer, citation dialog | 9, 10, 11, 12 |
| AC-8 model shown with each answer | 3, 6, 11, 12 |
| AC-9 documents survive a restart | 4, 7 |
| AC-10 Playwright journey in CI | 12 |
