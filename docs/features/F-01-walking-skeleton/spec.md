# F-01. Walking skeleton

- Status: approved
- Requirements: FR-01 (plain text only), FR-15, FR-60; FR-12 in a minimal form
- Related ADRs: 0002, 0003, 0005, 0006, 0008

## Why

Every later feature replaces one part of the question flow with a real one: Docling parsing (F-02), embeddings and Qdrant (F-03), a local LLM (F-06), the agent (F-07). This feature builds the whole flow end to end first, with the simplest parts that work, so each later feature swaps an adapter behind a port instead of building plumbing. It also proves the hard integration points early: file upload, a streamed answer over SSE, typed events in the generated client, and citations that resolve to stored text.

## Scope

- Upload a plain-text document (`.txt`, `.md`, UTF-8). The file is stored under the data directory and split into chunks along blank lines.
- List the uploaded documents.
- Ask a question. Retrieval is simple keyword overlap over the chunks, in memory. A fake chat model, clearly labelled as such, streams an extractive answer built from the best chunk and cites it.
- Answers stream to the UI as typed Server-Sent Events: text pieces, citations, end of answer.
- The UI has a document panel (upload, list) and a chat view with a streamed answer and clickable citations that show the quoted passage and its document.
- After an API restart, stored documents are loaded again and can be searched.
- First Playwright journey, run in CI.

## Out of scope

- PDF, DOCX, images, OCR, structure-aware chunking: F-02.
- Embeddings, Qdrant, hybrid search, reranking: F-03 and F-05.
- A real LLM, tool calling, structured output: F-06 and F-07.
- Full refusal behaviour and prompt-injection defence: F-07. Here only "no matching passage" is handled.
- Deleting or re-indexing documents (FR-07): F-03.
- Conversation history: each question stands alone.

## Acceptance criteria

- [x] AC-1: Given a UTF-8 `.txt` or `.md` file up to 5 MB, when it is uploaded, then the API returns `201` with the document id, title and number of chunks, the file is stored under the data directory, and the document appears in the document list. Proof: `test_documents_api.py::test_upload_returns_the_new_document`, `::test_uploaded_documents_are_listed`; `test_file_document_store.py::test_writes_only_under_the_documents_directory`.
- [x] AC-2: Given a file of another type, larger than 5 MB, or not valid UTF-8, when it is uploaded, then the API rejects it with `415`, `413` or `422` and the standard error body (PY-22), and nothing is stored. Proof: `test_documents_api.py::test_rejected_uploads_return_the_standard_error_and_store_nothing`, `::test_an_oversized_upload_is_not_read_beyond_the_limit`; `test_document_service.py` rejection tests.
- [x] AC-3: Given the same content is uploaded twice, then the second upload returns the existing document instead of a duplicate, and chunk ids are the same as the first time. Proof: `test_documents_api.py::test_uploading_the_same_content_twice_returns_the_same_document`; `test_chunking.py::test_chunks_carry_document_id_position_and_stable_id`.
- [x] AC-4: Given uploaded documents, when a question is asked, then the API streams text events, then at least one citation event, then an end event; every citation names a stored chunk, its document, and a quote that appears verbatim in that chunk. Proof: `test_chat_api.py::test_answer_is_a_stream_of_text_then_citation_then_end`, `::test_citation_events_carry_the_quoted_passage`; `test_question_service.py::test_citations_quote_their_chunk_verbatim`.
- [x] AC-5: Given no documents, or no chunk sharing a meaningful word with the question, when a question is asked, then the stream says that no relevant passage was found and contains no citation. Proof: `test_question_service.py::test_without_documents_no_relevant_passage_is_reported`, `::test_without_a_shared_word_no_relevant_passage_is_reported`; `test_chat_api.py::test_without_documents_the_stream_has_no_citation`; `ChatView.test.tsx` "shows no citations when no relevant passage was found".
- [x] AC-6: The SSE event types are part of the OpenAPI schema, and the generated TypeScript client exposes them. Proof: `test_chat_api.py::test_openapi_documents_the_event_stream_and_its_event_types`; `useChatStream.ts` uses the generated `ChatEvent`; `make check-api-client`.
- [x] AC-7: In the UI, when a user uploads a file, it appears in the document list; when they ask a question, the answer appears piece by piece, citations are shown under it, and opening a citation shows the quoted passage and the document title. Proof: `DocumentPanel.test.tsx` "uploads a file chosen in the labelled input and shows it in the list"; `ChatView.test.tsx` "shows the streamed answer…", "opens a citation…", keyboard test; `e2e/ask-question.spec.ts`.
- [x] AC-8: Every answer in the UI shows which model produced it; with the fake model it reads as a fake, not as an AI answer. Proof: `ChatView.test.tsx` "marks answers from a test model by its flag, not its name", "shows no test-model notice for a real model"; `test_question_service.py::test_end_event_names_the_model_and_reports_a_found_answer`.
- [x] AC-9: Given documents uploaded earlier, when the API restarts, then they are listed and searchable again. Proof: `test_documents_api.py::test_documents_survive_a_restart`; `test_chat_api.py::test_documents_are_searchable_after_a_restart`.
- [x] AC-10: A Playwright journey (upload, ask, see the answer and open a citation) passes locally and in CI against the real API with the fake model. Proof: `frontend/e2e/ask-question.spec.ts`, `make e2e` locally and CI job `E2E`.

## Evaluation cases

Not applicable: the fake model is deterministic and its behaviour is covered by tests. Evaluation starts with F-04.

## Decisions

1. **Retrieval for now.** Keyword overlap (lower-cased words, stop words ignored) in an in-memory index behind the `Retriever`/`VectorStore` port, so F-03 replaces it with embeddings and Qdrant.
2. **Fake model output.** Extractive and deterministic. It streams the best chunk's first sentences word by word, cites that chunk, and identifies itself as `fake-extractive`. No randomness.
3. **Persistence.** Store the original files under `ASSISTANT_DATA_DIR/documents/` and rebuild the in-memory index from them on startup (AC-9). No database yet.
4. **E2E against what.** Playwright against the real API with the fake model, started by the test itself. This tests the true integration, and is still fast and deterministic. A new CI job, `E2E`, becomes a required check after merge.
5. **Upload limits.** `.txt` and `.md`, UTF-8, at most 5 MB (GEN-42). Larger and other formats arrive with Docling in F-02.
