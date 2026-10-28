# Product Requirements: Offline Assistant

Status: accepted · Last updated: 2026-10-28

## 1. Problem

Organisations that want an AI assistant over their own documents often cannot send those documents to a cloud model: regulated data, classified or air-gapped environments, or simply no trust in a third party. Most assistant demos assume a cloud API and a network connection.

Local models are now good enough for many document tasks, but running them well is its own engineering problem: picking a model for the hardware, making tool calling reliable on weaker models, measuring quality instead of guessing, and shipping everything to a machine with no internet.

## 2. Product

A knowledge assistant that runs entirely on one machine. The user loads documents (PDF, DOCX, scans, photos), asks questions by text or voice, and gets answers with citations, optionally read aloud. No data leaves the machine, and it keeps working with the network switched off.

Default dataset: the EU AI Act and the GDPR, official texts in English and Polish. The dataset is replaceable; the same assistant over public NATO or EU documents, or over technical documentation, is a configuration change.

## 3. Audience

| Who | What they need |
|---|---|
| Compliance or legal analyst | Ask "what does the AI Act require for X?" and get the exact article, not a paraphrase from memory. |
| Engineer in a restricted environment | Install and run the assistant on a machine without internet, and verify that nothing phones home. |
| Technical evaluator | See measured trade-offs between local models and a cloud model: quality, latency, memory, cost. |

## 4. Goals

1. Answer questions over the loaded documents with correct citations (document, article, paragraph, page).
2. Refuse when the documents do not contain the answer.
3. Run fully offline on the reference machine, including voice in and out.
4. Compare several local models and one cloud model on the same evaluation set and publish the results.
5. Install from removable media on a machine with no network.

## 5. Non-goals

- Multi-user accounts, authentication, permissions.
- Cloud or Kubernetes deployment.
- Fine-tuning or training models.
- Mobile apps.
- Legal advice. The assistant cites and quotes; it does not interpret the law for a specific case.
- A polished design system. The UI is functional and clear, not a product launch.

## 6. Reference hardware

MacBook Pro 14", Apple M5 Pro, 64 GB unified memory, macOS 26.

64 GB lets us run models up to roughly 32B parameters at 4-bit quantisation, or a mixture-of-experts model such as Qwen3 30B-A3B, next to the embedding model, reranker, speech models and Qdrant. It also allows two LLMs loaded at once for side-by-side comparison.

A secondary profile targets a Linux machine with an NVIDIA GPU (rented for a few hours is enough) to show vLLM serving.

## 7. Functional requirements

Requirement IDs are stable; feature specs reference them.

### M1. Document ingestion and retrieval

- **FR-01** Upload PDF, DOCX, images (PNG, JPG) and scanned PDFs.
- **FR-02** Parse with structure preserved: headings, articles, paragraphs, tables, page numbers. OCR for scans.
- **FR-03** Chunk along the document's own structure (article, paragraph), never across an article boundary.
- **FR-04** Embed Polish and English text into one index with a multilingual model.
- **FR-05** Hybrid search: dense vectors plus keyword (BM25-style) search, fused.
- **FR-06** Rerank candidates with a cross-encoder; reranking can be switched off for comparison.
- **FR-07** List, re-index and delete documents.

### M2. Agent with tools

- **FR-10** A local LLM answers through tool calls:
  - `search_documents(query, filters)`: retrieval from M1,
  - `get_article(document, number)`: full text of one article,
  - `compare(a, b)`: two provisions side by side,
  - `save_note(title, content)`: write a note or checklist to a local file.
- **FR-11** Every factual statement in an answer carries a citation that resolves to a stored chunk.
- **FR-12** If retrieval finds nothing relevant, the assistant says so instead of answering.
- **FR-13** Tool calls and final answers use JSON schema structured output, validated, with a bounded number of retries.
- **FR-14** Document content is treated as data. Instructions inside documents are not followed.
- **FR-15** Answers stream token by token to the UI.

### M3. Voice

- **FR-20** Push-to-talk speech input, Polish and English (Whisper family).
- **FR-21** Spoken answers (Piper voices for Polish and English).
- **FR-22** Speech output starts after the first complete sentence, not after the full answer.

### M4. Images (optional)

- **FR-30** A photo or screenshot of a document is described and its fields extracted by a local vision model.
- **FR-31** The extracted content can be used as the question context, e.g. "does this consent form meet GDPR requirements?".

### M5. Model switching and evaluation

- **FR-40** The LLM is selected by configuration, without code changes. Candidates: Qwen3 (8B, 14B, 30B-A3B, 32B), Bielik, gpt-oss-20b, Gemma 3. Exact versions are fixed in an ADR after the first evaluation run.
- **FR-41** Claude via API is available only in an explicit comparison mode (see NFR-01).
- **FR-42** An evaluation set of 30–50 questions with expected answers and expected sources, in both languages, including out-of-scope questions.
- **FR-43** Evaluations measure answer correctness, citation accuracy, refusal behaviour, tool-call validity, and retrieval with and without the reranker.
- **FR-44** Performance measurements per model: time to first token, tokens per second, peak memory, cost (cloud only).
- **FR-45** Results are published as a table in the repository.

### M6. Deployment and observability

- **FR-50** One command starts the stack locally.
- **FR-51** Two serving profiles: native on macOS (Ollama or MLX) and vLLM on Linux with a GPU.
- **FR-52** Offline installation from removable media: container images and model weights, no network needed.
- **FR-53** Every conversation, tool call and model call is traced in a self-hosted Langfuse (optional profile).

### UI

- **FR-60** Chat view with streamed answers and clickable citations that open the source passage.
- **FR-61** Document library: upload, status of ingestion, delete.
- **FR-62** Model selector and a visible "offline" indicator showing whether comparison mode (network) is on.

## 8. Non-functional requirements

| ID | Requirement | How it is verified |
|---|---|---|
| NFR-01 | No network egress at runtime in the default mode. The only allowed outbound connection is the cloud model in comparison mode, behind an explicit flag. | CI runs the end-to-end suite with container networking disabled. |
| NFR-02 | No telemetry from any component. | Configuration checklist in the offline install guide; same CI check. |
| NFR-03 | Time to first token ≤ 3 s for a typical question on the reference hardware with the default model. | Performance run in M5. |
| NFR-04 | First spoken audio ≤ 4 s after the user stops speaking. | Performance run in M5. |
| NFR-05 | Ingesting the EU AI Act (~150 pages) takes ≤ 5 min. | Timed ingestion test. |
| NFR-06 | All documentation, code and commit messages in English. | Review. |
| NFR-07 | Only models and libraries with licences that allow this use. Licences listed in the README. | Review on every new dependency (ADR). |

NFR-03 to NFR-05 are initial targets. They are revised once, after the first measured baseline, and the revision is recorded in an ADR.

## 9. Quality targets

Measured by the evaluation suite on the default local model:

| Metric | Target |
|---|---|
| Citation accuracy (cited passage supports the claim) | ≥ 90 % |
| Correct refusal on out-of-scope questions | ≥ 90 % |
| Valid tool calls after retries | ≥ 95 % |
| Answer correctness (judged) | reported per model, no fixed target until the baseline |

A change that lowers any metric below its target, or by more than 5 points from the last recorded result, does not merge.

## 10. Milestones

| # | Scope | Demonstrable result |
|---|---|---|
| 0 | Documentation, standards, workflow tooling, repository skeleton, CI | This repository |
| 1 | Walking skeleton: upload a text file, fake LLM, answer in the UI, in Docker, in CI | End-to-end path works |
| 2 | M1 + M2 with one local model, simple UI | Offline RAG assistant with citations |
| 3 | M5: evaluation set, 3–4 models compared | Results table |
| 4 | M6: Docker Compose profiles, Langfuse, offline install guide | Recording with Wi-Fi off |
| 5 | M3: voice | Full voice demo |
| 6 | README, architecture diagram, 2–3 min recording | Public showcase |
| 7 | M4: images (optional) | Multimodal demo |

Milestones 1–3 are the minimum useful demo. Milestones 4–6 make it complete.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Tool calling on local models is unreliable | Structured output with grammar/schema enforcement, validation, bounded retries, measured in M5. |
| Docker on macOS has no access to the Apple GPU | Model servers run natively on the host on macOS (ADR 0007). |
| Polish legal text chunks badly | Structure-aware chunking on article/paragraph, verified by retrieval evals. |
| Scope grows past the time budget | Milestones are independently demonstrable; M4 is optional. |
| Model versions change monthly | Versions are pinned in configuration and an ADR; the evaluation set makes switching cheap. |

## 12. Open questions

- Default LLM: decided by the first evaluation run (milestone 3).
- MLX or Ollama as the default macOS serving profile: decided by the same run.
- Whether Langfuse is part of the default stack or an optional profile, given its footprint.
