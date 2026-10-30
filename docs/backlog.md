# Backlog

Ordered. Work starts at the top. Each feature gets a folder in [features/](features/) when its spec is written.

Status: `planned` → `spec` → `building` → `review` → `done`.

| ID | Feature | Requirements | Milestone | Status |
|---|---|---|---|---|
| F-00 | Repository skeleton: backend and frontend projects, Makefile, pre-commit, CI, import contract, API contract check | NFR-06 | 1 | done |
| F-01 | Walking skeleton: upload a text file, fake chat model, streamed answer with a citation in the UI | FR-01, FR-15, FR-60 | 1 | done |
| F-02 | Document parsing (Docling) and structure-aware chunking with stable chunk ids | FR-01–FR-03 | 2 | done |
| F-03 | Multilingual embeddings, Qdrant storage, hybrid search | FR-04, FR-05, FR-07 | 2 | done |
| F-04 | Evaluation harness: Promptfoo wired to the API, first retrieval cases (recall@k against expected chunks) | FR-42, FR-43 | 2 | done |
| F-04a | Article context in the index: article label and title indexed with each chunk, section titles not chunked, measured with `make eval` | FR-03, FR-05 | 2 | done |
| F-05 | Reranker, switchable, measured with and without | FR-06, FR-43 | 2 | done |
| F-06 | OpenAI-compatible chat adapter with tool calling, JSON schema output, validation and retries | FR-13, FR-40 | 2 | done |
| F-07 | Agent with tools, resolvable citations, refusal, prompt-injection defence | FR-10–FR-12, FR-14 | 2 | done |
| F-07a | `save_note` tool: notes and checklists written to the local notes directory | FR-10, AI-11 | 2 | done |
| F-08 | Chat UI with clickable citations, document library, model selector, offline indicator | FR-60–FR-62 | 2 | done |
| F-09a | Evaluation set of 40–50 questions with reference answers, judged correctness and citation support, measured on the default model | FR-42, FR-43 | 3 | building |
| F-09b | Comparison of 3–4 local models: performance and memory, published report, ADR with the final model and revised targets | FR-40, FR-44, FR-45 | 3 | planned |
| F-09c | Claude in comparison mode: adapter behind ASSISTANT_ALLOW_NETWORK, cost, as the reference in the report | FR-41, FR-44 | 3 | planned |
| F-10 | Docker Compose profiles and `make offline-check` in CI | FR-50, FR-51, NFR-01, NFR-02 | 4 | planned |
| F-11 | Langfuse tracing (optional profile) | FR-53 | 4 | planned |
| F-12 | Offline install bundle and guide | FR-52 | 4 | planned |
| F-13 | Push-to-talk speech input | FR-20 | 5 | planned |
| F-14 | Spoken answers, streamed by sentence | FR-21, FR-22 | 5 | planned |
| F-15 | Showcase: README results, diagrams, 2–3 min recording | – | 6 | planned |
| F-16 | Image input with a local vision model (optional) | FR-30, FR-31 | 7 | planned |

## Follow-ups

Small changes found during reviews, done as chores outside the feature that found them.

| Item | Found in | Status |
|---|---|---|
| Switch the backend test client from `httpx` to `httpx2` (Starlette deprecation warning), with a note in ADR 0011 | F-00 review #11 | planned |
| Route tests with injected fake services instead of the file-backed composition root | F-01 review #16 | done in F-03 |
| Use `found=false` in the UI for a proper "no answer" state | F-01 review #18 | done in F-07 |
| Refuse a non-local `ASSISTANT_QDRANT_URL` or `ASSISTANT_LLM_URL` unless network mode is on (Compose service names allowed) | F-03 review #15, F-06 review #13 | planned for F-10 |
| Index each chunk with its article number and title, and keep section titles out of chunks (retrieval baseline causes 1 and 2) | F-04 baseline | became F-04a |
| Record the highest out-of-scope similarity in the evaluation report, so the threshold margin is a measured figure | F-04a review #7 | done in F-05 |
| Let an answer say the passages do not cover the question without citing unrelated passages (the schema requires a citation today) | F-06 answer baseline (`ref-article-83`) | done in F-07 |
| Let the agent read an annex (e.g. Annex III) like an article, and route annex questions to the tools again | F-07 review #4 | planned for F-09b |
| List the local model only while its server answers, not only at startup | F-08 review #10 | planned for F-09b |
| Decide whether paragraph-level cases accept a sibling paragraph that answers too (dataset-only commit; cross-language cases done in dataset version 2) | F-04 baseline | planned after the indexing change |
