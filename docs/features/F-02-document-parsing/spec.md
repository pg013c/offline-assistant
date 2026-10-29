# F-02. Document parsing and structure-aware chunking

- Status: approved
- Requirements: FR-01, FR-02, FR-03; NFR-01, NFR-05, NFR-07
- Related ADRs: 0002, 0004, 0006, 0009, 0014

## Why

The assistant must cite "the exact article, not a paraphrase" (PRD §3). With plain-text uploads chunked at blank lines, a citation can only say which file it came from. This feature reads the real formats people have (PDF, DOCX, scans, photos), keeps the document's own structure, and cuts chunks along it, so every chunk knows its article, paragraph and page. Chunk ids stay stable across re-ingestion, which the evaluation datasets from F-04 depend on. Retrieval and the answering model do not change.

## Scope

- Upload PDF (text and scanned), DOCX, PNG and JPG in addition to `.txt` and `.md`. Parsing goes through a document parser port; the real adapter uses Docling, with OCR for scans and images.
- The parser keeps headings, paragraphs, tables and page numbers. Legal texts in English and Polish are recognised by their structure: articles (`Article 6` / `Artykuł 6`) and numbered paragraphs (`1.`, `2.`).
- Chunks follow that structure: one numbered paragraph of an article, or one paragraph under a heading for other documents. A chunk never crosses an article boundary. A part that is too long is split at sentence boundaries; a table stays whole.
- Each chunk records its location: heading path, article, paragraph and page where known. Citations carry the location, and the UI shows it next to the document title (for example "EU AI Act, Art. 6(2), p. 53").
- Chunk ids derive from the document checksum and the structural position, so the same file always gives the same ids.
- Parsing models are fetched by an explicit `make models` step; at runtime the parser runs with offline flags and fails with a clear error if a model is missing (ADR 0004).

## Out of scope

- Embeddings, Qdrant, hybrid search, deleting and re-indexing documents: F-03.
- Detecting the language of a chunk: F-03, with the multilingual embeddings.
- Images or charts inside documents as content: F-16.
- A real chat model and answer quality: F-06 and F-07. The fake model stays.
- Retrieval metrics on the full AI Act and GDPR: F-04. Here the fixtures are short excerpts.

## Acceptance criteria

- [x] AC-1: Given a text PDF, a DOCX file, a scanned PDF or a PNG/JPG photo of text within the upload limit, when it is uploaded, then the API returns `202` with the document in status `processing`; once parsing finishes its status is `ready` with a chunk count and page count, and its text is searchable. Proof: `tests/integration/test_docling_parser.py` (PDF, DOCX, scan, JPG and PNG photos), `test_document_service.py::test_ingestion_makes_the_document_ready_and_searchable`, `test_documents_api.py::test_upload_is_accepted_and_the_document_becomes_ready`, `DocumentPanel.test.tsx` "shows a document as processing…", `e2e/ask-question.spec.ts`.
- [x] AC-2: Given an excerpt of a legal act in English or in Polish, when it is ingested, then each numbered paragraph of each article is its own chunk, labelled with its article and paragraph number and the page it starts on. Proof: `test_docling_parser.py::test_each_numbered_paragraph_of_article_6_is_a_chunk_with_its_page` (EN, PL), `::test_chunk_ids_and_locations_match_the_snapshot`, `test_structured_chunking.py` article tests.
- [x] AC-3: Given any ingested document, then no chunk contains text from two articles, no chunk exceeds the maximum chunk size except a single table, and a table is never split. Proof: `test_structured_chunking.py::test_no_chunk_holds_text_from_two_articles`, `::test_a_long_paragraph_is_split_at_sentence_boundaries_within_the_limit`, `::test_a_word_longer_than_the_limit_is_cut_to_fit`, `::test_a_table_is_one_chunk_however_long`.
- [x] AC-4: Given the same file is ingested twice, or the API restarts, then the chunk ids and their locations are identical. Proof: `test_docling_parser.py::test_chunk_ids_and_locations_match_the_snapshot`, `::test_the_same_file_gives_the_same_chunks`, `test_document_service.py::test_restore_indexes_stored_chunks_without_parsing_and_resubmits_unfinished_files`, `test_documents_api.py::test_documents_survive_a_restart`, `test_docling_models.py` (pinned models).
- [x] AC-5: Given a file that cannot be parsed (corrupt, password-protected, longer than 500 pages, or with no extractable text), when it is uploaded, then the document's status becomes `failed` with a reason shown in the UI, and none of its chunks are searchable. A file over 50 MB or of another type is rejected at upload with `413`, `415` or `422` and the standard error body. Proof: `test_docling_parser.py::test_unreadable_files_raise_with_a_reason`, `::test_a_pdf_without_text_has_no_blocks`, `test_document_service.py` failure tests, `test_documents_api.py::test_a_document_without_text_fails_with_its_reason`, `::test_rejected_uploads_return_the_standard_error_and_store_nothing`, `DocumentPanel.test.tsx` "shows why a document could not be read".
- [x] AC-6: Given a citation in an answer, then its event carries the chunk location, the generated client exposes it, and the UI shows it next to the document title; a document without articles shows its heading and page instead. Proof: `test_chat_api.py::test_citation_events_carry_the_location_of_the_chunk`, `test_question_service.py::test_citations_carry_the_location_of_their_chunk`, `citationLabel.test.ts`, `ChatView.test.tsx` "shows where each cited passage is…", `make check-api-client`.
- [x] AC-7: Given a parsing model is missing, when the API starts, then it fails with a message naming the missing model and `make models`; no download is attempted at runtime. Proof: `test_settings.py::test_startup_fails_when_parsing_models_are_missing`, `::test_the_app_forbids_model_downloads`, `test_docling_models.py`, `test_docling_parser.py::test_missing_models_name_the_model_and_the_command`, `::test_a_missing_ocr_engine_is_named`; `make test-integration` runs with `HF_HUB_OFFLINE=1`.
- [x] AC-8: The Playwright journey uploads a PDF and opens a citation that shows the article and page. Proof: `frontend/e2e/ask-question.spec.ts` (`make e2e`, CI job `E2E`).

## Evaluation cases

Not applicable: neither retrieval nor the model changes. Chunking is deterministic and covered by tests. F-04 builds evaluation cases on the chunk ids this feature makes stable.

## Decisions

1. **Ingestion in the background.** Upload validates the file, stores it and returns `202` with the document in status `processing`. Parsing runs in the background; the status becomes `ready` or `failed` (with a reason), and the UI shows it in the document list until it settles.
2. **Upload limit.** At most 50 MB and 500 pages (GEN-42).
3. **OCR engine.** Tesseract with Polish and English language data, installed as a system package on macOS, Linux and in CI.
4. **Real parser in CI.** Integration tests with real Docling run in a new CI job, `Integration`, with models cached; it becomes a required check after merge.
5. **Fixtures.** Short excerpts (two or three articles) of the EU AI Act in English and Polish from EUR-Lex, reused under the Commission's reuse policy (Decision 2011/833/EU) with the source stated, plus generated DOCX, scan and photo fixtures.

ADR needed before the plan: Docling and Tesseract as dependencies, their licences (NFR-07), and how their models are fetched and pinned for offline use.
