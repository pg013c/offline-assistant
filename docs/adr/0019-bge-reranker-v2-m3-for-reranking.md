# 0019. Rerank with BGE reranker v2 M3, pinned and loaded offline

- Status: accepted
- Date: 2026-10-29
- Related: FR-06, FR-43, AI-31, NFR-03, F-05, ADR 0002, ADR 0004, ADR 0016, ADR 0017

## Context

Hybrid search (ADR 0017) scores the question and each passage separately, by dense similarity and by BM25. After F-04a every expected passage is in the top 10, but passages that cite "Article 83" or "Annex III" still outrank the article or annex itself. FR-06 asks for a cross-encoder that reads the question and the passage together, switchable so the evaluation can compare (FR-43).

The model must:

- handle Polish and English, and questions in one language over passages in the other;
- run in the API process on the reference hardware (Apple M5 Pro, 64 GB), on MPS or CPU (ADR 0007), fast enough for NFR-03;
- have a licence that allows a public portfolio project and its demo;
- be fetched ahead of time, pinned and checked like the other models (ADR 0004, ADR 0016).

## Decision

1. **Model:** `BAAI/bge-reranker-v2-m3`, Apache-2.0.
   - A 568M-parameter cross-encoder on the XLM-RoBERTa base of BGE-M3, trained for multilingual reranking.
   - Pinned to revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`. `make models` fetches `config.json`, `model.safetensors` (2.3 GB), the tokenizer files and `sentencepiece.bpe.model`, each checked by SHA-256 in `pinned_models.py` and again at startup.
2. **Runtime:** sentence-transformers' `CrossEncoder`, already a backend dependency for BGE-M3. No new library.
3. **Port and adapter:** a `Reranker` port (named in ADR 0002), a `BgeReranker` adapter and an in-memory fake for tests. Services see only the port.
4. **Offline:** loaded from `ASSISTANT_MODELS_DIR` with `HF_HUB_OFFLINE=1`, like BGE-M3. With reranking off, the model is neither checked nor loaded.

## Alternatives considered

- **`jinaai/jina-reranker-v2-base-multilingual`:** smaller (278M) and multilingual, but CC-BY-NC-4.0. A non-commercial licence does not fit a public portfolio project.
- **`mixedbread-ai/mxbai-rerank-base-v1` and `cross-encoder/ms-marco-MiniLM-L-6-v2`:** small and fast, but trained mostly on English. Polish questions and cross-language cases are half of the dataset.
- **An LLM as the reranker (from F-06):** no extra model, but a call per candidate, or one long prompt, costs seconds per question, and the LLM is the part we swap and benchmark.
- **ColBERT vectors from BGE-M3:** late interaction with no new model, but it needs a multi-vector field in Qdrant and a different index. That is a larger change, and it is not a cross-encoder.

## Consequences

- **Good:**
  - question and passage are read together, which suits exact references and paraphrases;
  - the same family and tokenizer as the embedder;
  - no new library.
- **Bad:**
  - 2.3 GB more to fetch in `make models` and in the CI model cache;
  - each question scores every candidate, which adds latency; F-05 measures it.
- **Follow-up:**
  - `pinned_models.py`, `make models` and the CI cache key;
  - the `Reranker` row in `architecture.md`;
  - the model in the README licence table.
