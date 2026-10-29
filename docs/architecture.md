# Architecture

Status: initial design, before implementation · Last updated: 2026-10-28

This document describes the target shape of the system. Decisions behind it are in [adr/](adr/). Requirements are in [prd.md](prd.md).

## 1. Context

```mermaid
flowchart LR
    user([User]) -- text, voice, files --> app[Offline Assistant<br/>one machine]
    app -- answers, citations, speech --> user
    app -. comparison mode only .-> claude[(Claude API)]
    media[(Removable media:<br/>images, model weights)] -- offline install --> app
```

Everything inside the box runs on one machine. The dotted line is the only network connection the system may make, and only with an explicit flag (ADR 0004).

## 2. Containers

```mermaid
flowchart TB
    subgraph host[Host machine]
        ui[Web UI<br/>React + Vite, static]
        api[API<br/>Python, FastAPI]
        qdrant[(Qdrant<br/>vectors + payload)]
        files[(Local storage<br/>documents, notes)]
        llm[LLM server<br/>Ollama / MLX / vLLM<br/>OpenAI-compatible]
        langfuse[Langfuse<br/>optional profile]
    end
    ui -- REST + SSE --> api
    api --> qdrant
    api --> files
    api -- OpenAI-compatible HTTP --> llm
    api -. traces .-> langfuse
```

The embedding model, reranker, speech-to-text and text-to-speech run inside the API process (or a worker it owns). Only the LLM runs in a separate server, because it is the component we swap and benchmark, and every serving option exposes the same OpenAI-compatible API (ADR 0003).

## 3. Backend structure: ports and adapters

```mermaid
flowchart LR
    subgraph api_layer[api]
        routes[FastAPI routes<br/>Pydantic schemas]
    end
    subgraph services[services]
        ingest[IngestService]
        rag[RetrievalService]
        agent[AgentService]
        voice[VoiceService]
    end
    subgraph domain[domain]
        model[Document, Chunk,<br/>Citation, Answer]
    end
    subgraph ports[ports]
        p1[ChatModel]
        p2[Embedder]
        p3[Reranker]
        p4[VectorStore]
        p5[DocumentParser]
        p6[SpeechToText]
        p7[TextToSpeech]
        p8[NoteStore]
    end
    subgraph adapters[adapters]
        a1[OpenAICompatibleChat]
        a2[BgeM3Embedder]
        a3[BgeReranker]
        a4[QdrantStore]
        a5[DoclingParser]
        a6[WhisperSTT]
        a7[PiperTTS]
        a8[FileNoteStore]
        f[Fake* adapters<br/>for tests]
    end
    routes --> services
    services --> domain
    services --> ports
    adapters -. implement .-> ports
```

Rules (ADR 0002):

- `domain` imports nothing outside the standard library and Pydantic.
- `services` depend on `ports` (Python `Protocol`s) and `domain`, never on `adapters`.
- `adapters` are the only place that imports third-party model, database or parsing libraries.
- Wiring happens in one composition root (`app.py`), driven by configuration. `settings.py`, `log.py` (structlog JSON setup) and `openapi.py` (schema export for the generated client) sit beside it, outside the layers.
- The rules are import-linter contracts in `backend/pyproject.toml`, checked by `make check`. Every model, database or parsing library is added to the forbidden list for `domain`, `ports` and `services` together with its ADR.
- Every port has a fake adapter. Unit tests use fakes; integration tests use real adapters.

### What is implemented (F-01 to F-03)

The diagram above is the target. The question flow runs end to end today; each part is replaced by a later feature behind the same kind of port:

| Port | Adapter now | Replaced by |
|---|---|---|
| `DocumentParser` | `RoutingDocumentParser`: `TextDocumentParser` for `.txt` and `.md`, `DoclingDocumentParser` for PDF, DOCX, PNG and JPG (pdfium text, Tesseract OCR `eng+pol`, models from `make models`, ADR 0015); `FakeDocumentParser` for tests | stays |
| `DocumentStore` | `LocalFileDocumentStore`: `data_dir/documents/<id><ext>` (original), `<id>.json` (metadata, status), `<id>.chunks.json`; `FakeDocumentStore` for tests | stays |
| `IngestionQueue` | `ThreadIngestionQueue`: one worker thread, so one parse holds model memory at a time; `FakeIngestionQueue` and `InlineIngestionQueue` for tests | stays |
| `Embedder` | `SentenceTransformerEmbedder`: BGE-M3, 1,024 dimensions, Polish and English, MPS on the Mac, pinned and verified (ADR 0017); `FakeEmbedder` for tests | stays; F-09 compares models |
| `ChunkIndex` | `QdrantChunkIndex`: one collection per embedding model with a dense vector, a BM25 sparse vector (Qdrant's IDF modifier) and the chunk as payload, both halves fused by reciprocal rank in one query, ties broken by dense similarity; `InMemoryChunkIndex` for tests | reranking on top (F-05) |
| `ChatModel` | `FakeExtractiveChatModel` (`fake-extractive`): quotes the best passage, labelled as a test model in the UI | OpenAI-compatible local models (F-06), the agent (F-07) |

`create_app(settings, adapters)` takes the adapters to use; `build_adapters` wires the real ones, and route tests pass in-process fakes. At startup every model is checked against its pinned hashes (`pinned_models.py`), Tesseract against its languages and Qdrant against `ASSISTANT_QDRANT_URL`; each failure names what is missing and the command that fixes it (`make models`, `make qdrant`). The process runs with the Hugging Face offline flags. `ASSISTANT_DOCUMENT_PARSER=text-only` reads text and Markdown without Docling.

**Ingestion.** `POST /api/documents` checks type (PDF, DOCX, PNG, JPG, TXT, MD), size (50 MB) and, for text, UTF-8, stores the original with status `processing`, queues ingestion and answers `202`. The job parses the file into blocks (headings, paragraphs, list items, tables, with pages), chunks them and indexes the chunks; the document ends `ready` with chunk and page counts, or `failed` with a reason (locked, corrupt, over 500 pages, no text). On restart the index is reconciled with the store: ready documents it lacks are added from their stored chunks without parsing, chunks of deleted documents are removed, and unfinished documents are queued again. A new embedding model gets a new, empty collection that fills the same way; the collections of earlier models are kept on purpose, so F-09 can compare models without embedding the corpus again. `DELETE /api/documents/{id}` removes a document, its files and its chunks; `POST /api/documents/{id}/reindex` parses it again with the same chunk ids. The UI refreshes the list while a document is processing.

**Chunking** (`domain.chunk_document`). Chunks follow the document's structure: one paragraph with the list items after it, one table, or, in legal texts, one numbered paragraph of an article (`Article 6` / `Artykuł 6`, paragraphs `1.`, `2.`) with its points and subparagraphs. No chunk crosses an article or heading; text over 2,000 characters is split at sentence ends. Each chunk records its location (heading path, article, paragraph, page). Chunk ids are `<document id>:<position>`, and the document id is the SHA-256 of the uploaded bytes, so the same file always gives the same ids.

**Retrieval.** A question is embedded with BGE-M3 and split into BM25 terms (`domain.keywords`: lower-cased words in any script, stable SHA-256 token ids, saturated term frequency). Qdrant ranks chunks by dense similarity and by BM25 and fuses the rankings. Dense search makes questions find passages across languages and wording; BM25 keeps exact terms such as "Annex III" on top. Passages below `ASSISTANT_MIN_SIMILARITY` (dense cosine, 0.5) are dropped: on the fixtures, unrelated questions reach 0.33 and relevant passages start near 0.6.

**Answers.** The chat endpoint streams `text`, `citation` and `end` events. A citation carries the chunk location, which the UI shows as "Art. 6(2), p. 53", or the nearest heading and page. With no passage over the threshold the stream says so and has no citation.

## 4. Main flow: a question

```mermaid
sequenceDiagram
    participant UI
    participant API
    participant Agent as AgentService
    participant LLM as ChatModel
    participant RAG as RetrievalService
    participant VS as VectorStore
    UI->>API: POST /chat (question)
    API->>Agent: answer(question)
    Agent->>LLM: messages + tool schemas
    LLM-->>Agent: tool_call search_documents
    Agent->>RAG: search(query)
    RAG->>VS: hybrid search
    VS-->>RAG: candidates
    RAG->>RAG: rerank
    RAG-->>Agent: chunks with source metadata
    Agent->>LLM: tool result (as data, delimited)
    LLM-->>Agent: final answer (JSON schema)
    Agent->>Agent: validate, check citations resolve, retry if invalid
    Agent-->>API: stream answer + citations
    API-->>UI: SSE events
```

Voice wraps this flow: speech-to-text before `answer`, and text-to-speech on each completed sentence of the stream.

## 5. Data model (initial)

| Entity | Key fields |
|---|---|
| Document | id, title, language, source file, checksum, ingestion status |
| Chunk | id, document id, article, paragraph, page, language, text, embedding |
| Citation | chunk id, quoted span |
| Answer | text, citations, refused flag, model id, timings |

Chunk identity is stable across re-ingestion of the same file (derived from document checksum and structural position), so evaluation datasets can reference chunks.

## 6. Deployment profiles

| Profile | LLM server | Everything else | Use |
|---|---|---|---|
| `mac` (default) | Ollama or MLX, native on the host | Docker Compose | Reference hardware; Docker on macOS cannot use the Apple GPU (ADR 0007) |
| `gpu` | vLLM in Docker Compose | Docker Compose | Linux with NVIDIA GPU |
| `observability` | — | adds Langfuse | Traces and timings |
| `compare` | adds the Claude adapter | — | Evaluation only; enables network egress |

## 7. Offline boundary

- No component downloads anything at runtime. Models are fetched by an explicit `make models` step, which is the only step that needs the network, and can be replaced by copying from removable media.
- Telemetry is disabled in every component that has it (Qdrant, Langfuse, Hugging Face libraries, Ollama, Docling).
- CI runs the end-to-end suite with container networking disabled (NFR-01).

## 8. Repository layout

```text
offline-assistant/
├── CLAUDE.md                 global rules for the coding agent
├── Makefile                  single entry point: dev, test, check, eval, offline-check
├── docker-compose.yml        profiles: mac, gpu, observability, compare
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── workflow.md           how work moves from idea to merge
│   ├── backlog.md            ordered feature list
│   ├── adr/                  architecture decision records
│   ├── standards/            engineering rules the agent and reviewer apply
│   ├── features/F-xx-name/   spec.md, plan.md, review.md per feature
│   └── evals/                published evaluation results
├── backend/                  Python package `assistant` (uv project)
├── frontend/                 React app (pnpm project)
├── evals/                    Promptfoo configs and datasets
├── scripts/                  model download, offline bundle, data fetch
└── .claude/                  skills, agents, hooks used to build this repository
```
