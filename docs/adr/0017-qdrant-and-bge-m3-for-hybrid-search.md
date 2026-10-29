# 0017. Hybrid search with BGE-M3 embeddings and BM25 in Qdrant

- Status: accepted
- Date: 2026-10-29
- Related: FR-04, FR-05, FR-07, NFR-01, NFR-05, NFR-07, F-03, ADR 0002, ADR 0004, ADR 0007, ADR 0016

## Context

F-03 replaces the in-memory keyword index with semantic, bilingual retrieval. The corpus is the EU AI Act and the GDPR in English and Polish: a few thousand chunks. Questions mix languages ("Kiedy system AI jest wysokiego ryzyka?" against the English text) and exact identifiers ("Annex III", "Article 6"). The architecture names Qdrant as the vector store and BGE-M3 as the embedder. Everything must run offline from pre-fetched models (ADR 0004), and stored chunks stay the source of truth, so the index can always be rebuilt from them.

## Decision

1. **Qdrant server 1.20.0.**
   - It runs in Docker as `qdrant/qdrant:v1.20.0`, pinned by digest `sha256:9bfc89f9…a424cd2`, with telemetry disabled (`QDRANT__TELEMETRY_DISABLED=true`) and data under `ASSISTANT_DATA_DIR/qdrant`.
   - `make qdrant` starts it for development, and CI runs it as a service container. F-10 moves it into the Compose profile.
   - The API reaches it at `ASSISTANT_QDRANT_URL` with `qdrant-client` (Apache-2.0).
2. **One collection per embedding model**, holding for each chunk:
   - a dense vector;
   - a sparse BM25 vector;
   - a payload with the chunk id, document id, location and text.

   Its name includes the model and a schema version, so a new model gets a new collection, rebuilt from the stored chunks.
3. **Embedder: BGE-M3** (`BAAI/bge-m3`, MIT, 568M parameters, 1,024 dimensions, Polish and English, 8,192 tokens).
   - It runs through `sentence-transformers` (Apache-2.0) on the PyTorch already in the project, with MPS on the Mac and CPU in CI and Docker (ADR 0007).
   - It is pinned to commit `5617a9f6` with file hashes, fetched by `make models` and verified at startup, like the parsing models (ADR 0016).
   - We fetch only what the dense model needs: weights, configuration and tokenizer. The ONNX copy, the ColBERT and sparse heads, and the images are left out.
4. **Keyword half: BM25**, as a sparse vector built from our own tokenizer (lower-case word tokens, no stemming), with term frequencies saturated as in BM25. Qdrant's IDF modifier supplies the document frequencies.
5. **Fusion:** both rankings come from one Qdrant query (prefetch dense and sparse, fused with reciprocal rank fusion).
6. **"No relevant passage"** is decided on dense cosine similarity, with a configurable threshold.

## Alternatives considered

- **Qdrant embedded local mode** (inside the API process) – no Docker needed, but slower, single-process, and missing some server features. The production shape (F-10) is a server anyway.
- **pgvector, Chroma or LanceDB** – fine stores, but the architecture, the hybrid query API and payload filters fit Qdrant, and a second store would add no value to the comparison this project is about.
- **multilingual-e5-large** (MIT) – a strong multilingual model, but 512 tokens of context against BGE-M3's 8,192, and no learned sparse vectors to compare later.
- **FlagEmbedding for BGE-M3** – gives the learned sparse vectors too, but adds a package for a second retrieval path F-04 has not asked for yet. sentence-transformers covers the dense model.
- **BGE-M3 learned sparse vectors** instead of BM25 – multilingual, but less exact for identifiers; F-04 can compare them.
- **fastembed's BM25** – adds onnxruntime and its own model download for something a tokenizer and Qdrant's IDF modifier already do.

## Consequences

- Good: cross-language and paraphrased questions find passages; exact terms still rank first through BM25; the index is disposable and rebuilds from stored chunks.
- Bad: `make dev` and the test suites that touch Qdrant need Docker running. The models directory grows by about 2.3 GB.
- Bad: BGE-M3's weights are a PyTorch pickle (`pytorch_model.bin`) with no safetensors copy at the pinned commit. The pinned hash and transformers' weights-only loading limit the risk.
- Bad: on CPU, embedding the full corpus takes minutes, so NFR-05 is measured on the Mac with MPS.
- Follow-up:
  - `make qdrant`;
  - `ASSISTANT_QDRANT_URL` in `.env.example`;
  - the CI service container;
  - Qdrant, qdrant-client, BGE-M3, sentence-transformers and scikit-learn in the README licence table;
  - Qdrant joins the telemetry checklist (ADR 0004);
  - `qdrant_client` and `sentence_transformers` added to the import-linter forbidden list for the inner layers.
