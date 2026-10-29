# F-03. Multilingual embeddings, Qdrant and hybrid search

- Status: approved
- Requirements: FR-04, FR-05, FR-07; FR-12 in the same minimal form as F-01; NFR-01, NFR-05, NFR-07
- Related ADRs: 0002, 0004, 0007, 0015, 0016

## Why

Keyword overlap finds a passage only when the question uses the document's words. A user who asks in Polish about an English act, or says "facial recognition" where the act says "remote biometric identification", gets nothing. This feature makes retrieval semantic and bilingual. Every chunk gets a multilingual embedding. Search fuses dense similarity with keyword matching, so exact terms ("Article 6", "Annex III") still win. Chunks and vectors are stored in Qdrant instead of process memory. It also adds the missing document operations: delete and re-index. The answering model stays the test model; F-04 measures retrieval quality on these results.

## Scope

- Each chunk is embedded with one multilingual model for Polish and English. Its vectors and payload (document, location, text) are stored in Qdrant.
- Search runs dense and keyword retrieval and fuses the two rankings into one list, best first.
- A question with no sufficiently similar chunk still gets "no relevant passage" and no citation.
- Stored chunks remain the source of truth; the Qdrant collection is derived from them:
  - startup fills an empty or missing collection from the stored chunks, without parsing again;
  - changing the embedding model rebuilds the collection.
- `DELETE /api/documents/{id}` removes the document, its files and its vectors.
- `POST /api/documents/{id}/reindex` parses and embeds the document again.
- The document panel offers both actions.
- Route tests use fake services instead of the file-backed composition root (F-01 review follow-up).
- Models come from `make models` and are pinned and verified, as in ADR 0016.

## Out of scope

- Reranking: F-05.
- Retrieval metrics and the evaluation harness: F-04. Here retrieval is tested on a few fixed cases.
- Real answers from a language model: F-06 and F-07.
- Docker Compose profiles for the whole stack and `make offline-check`: F-10. This feature adds only what Qdrant needs to run locally and in CI.

## Acceptance criteria

- [ ] AC-1: Given a document becomes ready, then each of its chunks is stored in Qdrant with a dense vector, a keyword vector and a payload holding the chunk id, document id, location and text.
- [ ] AC-2: Given the English AI Act excerpt, when a question is asked in Polish about the conditions of Article 6(1), then a chunk of Article 6 is among the top 3 results. The same holds for an English question about the Polish excerpt.
- [ ] AC-3: Given a question that quotes an exact term ("Annex III", "Article 6"), then a chunk containing that term ranks first, even if another chunk is semantically closer.
- [ ] AC-4: Given a question unrelated to every stored chunk, or no documents, then the stream says no relevant passage was found and has no citation.
- [ ] AC-5: Given a ready document, when it is deleted, then it disappears from the list, its files and vectors are removed, and no answer cites it. Deleting an unknown id returns `404` with the standard error body.
- [ ] AC-6: Given a document, when it is re-indexed, then it goes through `processing` to `ready`, and its chunk ids are unchanged.
- [ ] AC-7: Given documents stored earlier, when the API starts with an empty Qdrant collection or after the embedding model changed, then the collection is rebuilt from stored chunks without parsing, and search works.
- [ ] AC-8: Given the embedding model is missing or differs from its pinned hash, or Qdrant cannot be reached, then the API fails at startup with a message saying what is missing and how to fix it. No model is downloaded at runtime.
- [ ] AC-9: In the UI, a user can delete a document and re-index it from the document panel; the list reflects the change.

## Evaluation cases

Not applicable as an evaluation run yet: F-04 builds the harness and the retrieval metrics. AC-2 and AC-3 are fixed integration test cases on the AI Act fixtures, and they become the first evaluation cases in F-04.

## Decisions

1. **Qdrant runs as a server** in Docker:
   - started by `make qdrant` for development;
   - a service container in CI;
   - part of the Compose profile in F-10.

   The API connects through `ASSISTANT_QDRANT_URL`. Docker Desktop must be running for `make dev`.
2. **Embedding model:** BGE-M3 through sentence-transformers on PyTorch, with MPS on the Mac and CPU elsewhere. It is pinned and fetched by `make models` like the parsing models.
3. **The keyword half is BM25:** word tokens from our own tokenizer (lower-cased, no stemming) as sparse vectors with Qdrant's IDF weighting. Dense and keyword rankings are fused with reciprocal rank fusion. F-04 can compare it with BGE-M3's learned sparse vectors.
4. **"No relevant passage"** when no chunk reaches a configurable dense cosine similarity, starting at 0.5 and tuned on the fixtures. F-04 measures the threshold; F-07 owns full refusal.
5. **Delete and re-index** are two buttons per document in the panel; the fuller library stays in F-08.

ADR needed before the plan: Qdrant (server and client), BGE-M3 and sentence-transformers as dependencies, with licences, pinned versions and offline use.
