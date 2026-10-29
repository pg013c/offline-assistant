# F-03. Plan

- Status: approved
- Spec: [spec.md](spec.md)

## Research

- **`ChunkIndex` port:** `add(chunks)` and `search(query, limit) -> list[ScoredChunk]`.
  - Its only adapter, `KeywordChunkIndex`, counts shared words.
  - It is used by `DocumentService` (`add` on ingestion and restore) and `QuestionService` (`search`, then the best chunk is cited).
  - Unit tests use the keyword index as if it were a fake. `tests/contract/test_chunk_index.py` describes keyword behaviour ("ranks by shared words"), which semantic search will not meet.
- **Stored chunks are already the source of truth.** `restore()` indexes them without parsing and requeues documents without chunks, so a rebuilt Qdrant collection needs no parsing.
- **No delete or re-index yet.**
  - `DocumentStore` has no `delete`.
  - `DocumentService.ingest` runs only for `processing` documents, so re-indexing is "set to processing and queue".
- **Pinned models.** `adapters/docling_models.py` pins the parsing models, `make models` fetches them, and `DoclingDocumentParser.ensure_ready` verifies them. BGE-M3 needs the same treatment.
- **Routes still test the real composition root** with the text parser (F-01 review #16). With Qdrant and BGE-M3, that would need a server and 2.3 GB of weights, so routes must get fake adapters.
- **Risks:**
  - BGE-M3 on CPU is slow (CI).
  - Qdrant must run for `make dev`, the Integration job and the E2E job.
  - The E2E journey must not write into the development collection.
  - A fused ranking has no absolute score, so the threshold uses the dense similarity of each hit.
  - The test model cites only the best chunk, so ranking order matters for the journey.

## Design

### Domain

- `bm25_terms(text) -> dict[int, float]`, in `domain/keywords.py`:
  - lower-cased word tokens in any script, with numbers kept ("6", "iii");
  - token ids are a stable 31-bit hash of the token;
  - term frequency is saturated as in BM25 (`k1 = 1.2`), with no length normalisation, because chunks are short and bounded.
- `ScoredChunk` gains `similarity`: the dense cosine similarity, or 0 when only the keyword half found it.

### Ports

- `Embedder`: `model_id`, `dimensions`, `embed(texts) -> list[list[float]]`, `embed_query(text) -> list[float]`.
- `ChunkIndex`:
  - `add(chunks)`;
  - `search(query, limit) -> list[ScoredChunk]` (fused order);
  - `remove_document(document_id)`;
  - `document_ids() -> set[str]`.
- `DocumentStore` gains `delete(document_id)`.

### Adapters

- `SentenceTransformerEmbedder`: BGE-M3, normalised vectors, MPS when available, from the verified models directory.
- `QdrantChunkIndex(client, embedder, collection)`:
  - collection `<prefix>-<model>-v1`, with a dense vector (cosine) and a sparse `bm25` vector (IDF modifier);
  - payload: chunk id, document id, position, location, text; point ids are UUIDs derived from chunk ids;
  - one query that prefetches both halves and fuses them with reciprocal rank fusion, then reads the similarity of the returned points;
  - `ensure_ready()` fails when Qdrant cannot be reached.
- Fakes:
  - `FakeEmbedder`: deterministic hashed bag-of-words vectors, with a small fixed table of English–Polish word pairs for cross-language tests;
  - `InMemoryChunkIndex`: fake embedder plus `bm25_terms`, fused the same way.
- `KeywordChunkIndex` goes.
- `PINNED_MODELS` becomes a list of pinned repositories, each with its own directory, files and hashes. BGE-M3 is added at `5617a9f6`. `make models` and the startup checks cover every pinned model.

### Services

- `DocumentService.delete(id)`: store and index; an unknown id raises `DocumentNotFound`.
- `DocumentService.reindex(id)`: remove the document's vectors, set it to `processing`, queue it.
- `restore()` reconciles the index with the store:
  - adds the chunks of ready documents the index lacks;
  - removes vectors of documents the store no longer has;
  - requeues the rest as today.
- `QuestionService` drops hits below `min_similarity` before citing.

### Composition root, settings, API

- **Composition root:** `create_app(settings, adapters=None)`. `build_adapters(settings)` wires the real ones; tests pass fakes.
- **Settings:**
  - `ASSISTANT_QDRANT_URL` (default `http://127.0.0.1:6333`);
  - `ASSISTANT_QDRANT_COLLECTION_PREFIX` (default `assistant`; the E2E journey uses its own);
  - `ASSISTANT_MIN_SIMILARITY` (default 0.5);
  - `ASSISTANT_DOCUMENT_PARSER` stays.
- **Startup** checks the embedder models and Qdrant, as it does for Docling.
- **API:**
  - `DELETE /api/documents/{id}` returns `204`, or `404` with the standard body;
  - `POST /api/documents/{id}/reindex` returns `202` with the document, or `404`;
  - then `make api-client`.

### UI and tooling

- **UI:** the document panel gets per-document "Re-index" and "Delete" buttons; "Delete" asks for confirmation inline. Mutations invalidate the list.
- **`make qdrant`:**
  - starts the pinned Qdrant image with telemetry off, data under `ASSISTANT_DATA_DIR/qdrant`, on port 6333;
  - it is idempotent, and it checks the port first and names the container that uses it.
- **CI:**
  - Integration and E2E get a Qdrant service container;
  - the model cache key includes the new pins.

## Steps

### Step 1. Dependencies, Qdrant target and settings

- Kind: setup (one `build` commit)
- Change:
  - `uv add qdrant-client sentence-transformers` (ADR 0017);
  - `make qdrant`;
  - `.env.example`;
  - import-linter forbids `qdrant_client` and `sentence_transformers` in the inner layers;
  - README licences and setup.
- Done when: `make qdrant` serves `/readyz` and `make check` is green.
- [x] green

### Step 2. Pinned models for every model, BGE-M3 included

- Kind: code
- Tests first, in `tests/unit/adapters/test_pinned_models.py`:
  - every pinned repository has a 40-hex commit, a directory and file hashes;
  - verification reports a missing or changed file by repository;
  - BGE-M3 is pinned with its weights and tokenizer files and without its ONNX, ColBERT and sparse files.
- Change: `adapters/pinned_models.py` (from `docling_models.py`), `scripts/download_models.py`, the Docling parser's readiness check, the CI cache key.
- [x] red
- [x] green

### Step 3. BM25 terms

- Kind: code
- Tests first, in `tests/unit/domain/test_keywords.py`:
  - tokens are lower-cased and keep Polish letters and numbers;
  - the same token always gets the same id, across processes (a fixed expected id);
  - repeated terms saturate;
  - empty text gives no terms.
- Change: `domain/keywords.py`.
- [x] red
- [x] green

### Step 4. Embedder port, fake and BGE-M3

- Kind: code
- Tests first:
  - `tests/contract/test_embedder.py`, run against the fake:
    - vectors have the stated dimensions and unit length;
    - the same text gives the same vector;
    - related texts are closer than unrelated ones.
  - `tests/integration/test_bge_m3.py`:
    - the same contract against BGE-M3;
    - a Polish and an English sentence about high-risk AI are closer than either is to a sentence about cooking;
    - the model loads from the pinned directory with `HF_HUB_OFFLINE=1`.
- Change: `ports/embedder.py`, `adapters/fakes/embedder.py`, `adapters/sentence_transformer_embedder.py`.
- [x] red
- [x] green

### Step 5. Chunk index port and in-memory fake

- Kind: code
- Tests first, in `tests/contract/test_chunk_index.py` (rewritten), run against `InMemoryChunkIndex`:
  - a chunk sharing the meaning of the query ranks first;
  - a chunk containing an exact query term ranks above a merely related one;
  - results carry a dense similarity;
  - the limit is respected;
  - an empty index or an empty query returns nothing;
  - `remove_document` removes all of a document's chunks;
  - `document_ids` lists indexed documents;
  - adding the same chunks again does not duplicate them.

  Service tests switch to the fake index.
- Change: `ports/chunk_index.py`, `adapters/fakes/chunk_index.py`, removal of `adapters/keyword_index.py`.
- [x] red
- [ ] green

### Step 6. Qdrant chunk index

- Kind: code
- Tests first:
  - the chunk index contract also runs against `QdrantChunkIndex` with the fake embedder (marker `integration`, a fresh collection per test);
  - `tests/integration/test_qdrant_chunk_index.py`:
    - points carry the payload of AC-1;
    - a new embedding model id gives a new collection;
    - `ensure_ready` names the URL and `make qdrant` when Qdrant is down.
- Change: `adapters/qdrant_chunk_index.py`; CI job `Integration` gets a Qdrant service.
- [ ] red
- [ ] green

### Step 7. Similarity threshold for "no relevant passage"

- Kind: code
- Tests first, in `test_question_service.py`:
  - hits below `min_similarity` are not cited;
  - when none is left, the stream reports no relevant passage and `found=False`;
  - the best remaining hit is cited.
- Change: `services/questions.py`.
- [ ] red
- [ ] green

### Step 8. Delete, re-index and index reconciliation

- Kind: code
- Tests first:
  - the store contract: `delete` removes metadata, original and chunks, and deleting twice is harmless;
  - `test_document_service.py`:
    - delete removes the document from store and index;
    - an unknown id raises `DocumentNotFound`;
    - re-index sets `processing`, removes the vectors, and after ingestion the document is ready with the same chunk ids;
    - restore adds missing documents to the index, removes vectors of deleted ones, and does not parse ready documents.
- Change: `ports/document_store.py`, both store adapters, `services/documents.py`, `domain/errors.py`.
- [ ] red
- [ ] green

### Step 9. Composition root with injectable adapters, route tests with fakes

- Kind: code
- Tests first:
  - `tests/conftest.py` builds apps from fake adapters (fake store, fake index with fake embedder, text parser, inline queue), and route tests use it (F-01 review #16);
  - `test_settings.py`:
    - startup fails naming the embedding model and `make models` when BGE-M3 is missing;
    - startup fails naming `ASSISTANT_QDRANT_URL` and `make qdrant` when Qdrant is unreachable;
    - the new settings are read from the environment.
- Change: `app.py`, `settings.py`, `tests/conftest.py`.
- [ ] red
- [ ] green

### Step 10. Delete and re-index endpoints

- Kind: code
- Tests first, in `test_documents_api.py`:
  - `DELETE` returns `204` and the document is gone from the list and from answers;
  - `DELETE` and re-index of an unknown id return `404` with the standard body;
  - re-index returns `202` with `processing`, and the document settles `ready`.
- Change: `api/routes/documents.py`, `api/errors.py`, `make api-client`.
- [ ] red
- [ ] green

### Step 11. Delete and re-index in the document panel

- Kind: ui
- Tests first, in `DocumentPanel.test.tsx`:
  - "Delete" asks for confirmation, then the document leaves the list;
  - cancelling keeps it;
  - "Re-index" shows the document as processing and the list refreshes until it is ready;
  - an API error is shown.
- Change: `features/documents/useDocuments.ts`, `DocumentPanel.tsx`.
- [ ] red
- [ ] green

### Step 12. Retrieval cases on the AI Act excerpts

- Kind: code (fixed retrieval cases; they become evaluation cases in F-04)
- Tests first, in `tests/integration/test_hybrid_search.py`, with real BGE-M3 and Qdrant:
  - a Polish question about Article 6(1) finds an Article 6 chunk of the English excerpt in the top 3, and an English question finds one of the Polish excerpt;
  - "Annex III" ranks a chunk containing it first;
  - an unrelated question (cooking) stays below the threshold.
- Change: the threshold default, if the cases show 0.5 is wrong.
- [ ] red
- [ ] green

### Step 13. Journey on the full stack

- Kind: ui
- Tests first, in `frontend/e2e/ask-question.spec.ts`:
  - the journey asks its question in Polish and still opens Art. 6(1);
  - a second journey deletes the document and sees "no relevant passage".
- Change:
  - Playwright starts the API with `ASSISTANT_QDRANT_COLLECTION_PREFIX=e2e`;
  - `make e2e` requires Qdrant;
  - the CI job `E2E` gets the Qdrant service and the models.
- [ ] red
- [ ] green

### Step 14. Documentation

- Kind: setup (one `docs` commit)
- Change: `docs/architecture.md` (ports, adapters, Qdrant, retrieval flow, what is implemented), README (setup with Docker and `make qdrant`, status), `testing.md` if needed, backlog follow-up #16 done.
- [ ] green

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 vectors and payload in Qdrant | 4, 6 |
| AC-2 cross-language retrieval | 4, 12, 13 |
| AC-3 exact terms rank first | 3, 5, 12 |
| AC-4 no relevant passage | 7, 12, 13 |
| AC-5 delete | 8, 10, 13 |
| AC-6 re-index keeps chunk ids | 8, 10 |
| AC-7 rebuild from stored chunks | 6, 8 |
| AC-8 startup checks, no downloads | 2, 6, 9 |
| AC-9 delete and re-index in the UI | 11, 13 |
