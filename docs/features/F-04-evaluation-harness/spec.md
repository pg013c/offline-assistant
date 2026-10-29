# F-04. Evaluation harness and first retrieval cases

- Status: approved
- Requirements: FR-42 (first part), FR-43 (retrieval), FR-45; AI-31, AI-61; TEST-20 to TEST-22
- Related ADRs: 0004, 0006, 0017

## Why

From here on, every change to retrieval, prompts or models is accepted on measured numbers, not on a few tests that happen to pass (ADR 0006). F-03 fixed four retrieval cases by hand. This feature builds the harness behind `make eval`: a versioned dataset of questions with expected sources, a corpus that every machine indexes the same way, and metrics with a recorded baseline. The first suite measures retrieval alone, because retrieval is the only model behaviour so far. F-05 (reranker) is the first change to be judged by it. F-06 to F-09 add answer, citation and refusal metrics to the same harness.

## Scope

- **Corpus:** the AI Act and the GDPR, official texts in English and Polish (four PDFs). They are fetched by `make eval-corpus` and pinned by SHA-256, like models, and indexed through the normal ingestion path.
- **Search endpoint:** `POST /api/search` returns the ranked passages for a query, with similarity and location. The harness uses it, and it is useful for debugging.
- **Dataset:** 24 retrieval cases in `evals/`, each with:
  - an id, a language, a question;
  - expected sources: a document and an article with its paragraph, or `none` for out-of-scope;
  - the expected behaviour (`answer` or `refuse`).

  The cases cover both languages, cross-language questions, exact references, questions that span several articles, and out-of-scope questions.
- **Metrics:** recall@3 and recall@10, MRR, the share of out-of-scope questions with no passage over the threshold, and the share of in-scope questions wrongly left without a passage. Each metric states how many cases it is based on.
- **Records:** each run writes a dated report with:
  - the metrics;
  - the cases that missed;
  - the model and Qdrant versions, the configuration, the dataset version and the hardware (AI-61).

  The first run is published as the baseline in `docs/evals/`.
- **Regression gate:** `make eval` compares with the recorded baseline and fails when a metric drops by more than 5 points (PRD §9).

## Out of scope

- Answer correctness, citation accuracy, refusal by a language model, tool calls: F-06 and F-07 add these to the same harness.
- The full 30–50 question set with reference answers, model comparison and the published comparison table: F-09.
- Reranking: F-05, measured with this harness.
- Running evaluations in CI on every push (ADR 0006: on demand).

## Acceptance criteria

- [x] AC-1: Given `make eval-corpus`, then the four PDFs are downloaded, checked against their pinned hashes, and nothing is downloaded again if they are present. Proof: `evals/tests/test_corpus.py::test_only_missing_files_are_downloaded`, `::test_a_download_with_another_hash_stops_and_is_not_kept`, `::test_the_corpus_pins_the_ai_act_and_the_gdpr_in_english_and_polish`; `make eval-corpus` run twice.
- [x] AC-2: Given the corpus, when the evaluation runs, then it indexes the corpus through the API into its own collection and data directory, leaving the development data untouched. Proof: `evals/tests/test_run.py` (own API, data directory and collection; other collections untouched; fresh index per run), `test_run_preparation.py` (busy port refused, only own collections dropped).
- [x] AC-3: `POST /api/search` with a query and a limit returns at most that many passages, best first, each with chunk id, document, location, text and similarity; an empty or too long query returns `422` with the standard error body. Proof: `backend/tests/unit/api/test_search_api.py`, `test_question_service.py` search tests.
- [x] AC-4: Every case in the dataset validates against a schema (TEST-20), and every expected source resolves to at least one chunk of the indexed corpus; a case that resolves to nothing fails the run before any metric is computed. Proof: `evals/tests/test_dataset.py`, `test_resolve.py`, `backend/tests/unit/api/test_documents_api.py` chunk listing tests; every source resolved in the baseline run.
- [x] AC-5: Given the indexed corpus, when `make eval` runs, then it reports recall@3, recall@10, MRR, the out-of-scope and in-scope refusal shares, each with its case count, and lists the cases that missed. Proof: `evals/tests/test_metrics.py`, `test_run.py`; [baseline record](../../evals/2026-10-29-retrieval-baseline.md).
- [x] AC-6: Every run writes a report with model versions, collection, configuration, dataset version and hardware. The first run is committed as the baseline in `docs/evals/`. Proof: `evals/tests/test_report.py`, `test_run.py` (corpus hashes, indexing time); `docs/evals/retrieval-baseline.json` and the baseline record.
- [x] AC-7: Given a recorded baseline, when a later run drops any metric by more than 5 points, then `make eval` exits with an error naming the metric. Otherwise it passes. Proof: `evals/tests/test_gate.py`, `test_main.py::test_make_eval_exits_with_an_error_naming_each_regression`; a repeat `make eval` passes the gate.
- [x] AC-8: The evaluation runs offline once the models and corpus are present. Evaluation tooling sends no telemetry. Proof: `evals/tests/test_promptfoo.py` (telemetry, updates and sharing off; `--no-write`), `test_run_preparation.py` (no development settings); `make eval` runs with `HF_HUB_OFFLINE=1`.

## Evaluation cases

This feature creates the first evaluation set; its cases are the deliverable (TEST-21). They are added in their own commit, before the code that runs them (TEST-22).

| Kind | Count | Example |
|---|---|---|
| English, single article | 6 | "Which practices are prohibited for AI systems that exploit vulnerabilities?" → AI Act Art. 5(1) |
| Polish, single article | 6 | "Kto jest administratorem danych?" → GDPR Art. 4 |
| Cross-language (EN question, PL text only, and back) | 4 | Polish question, expected English Art. 6(1) |
| Exact reference | 3 | "What does Annex III cover?" → AI Act Art. 6(2) |
| Spans articles | 2 | "What must providers and deployers of high-risk systems each do?" → Art. 16, Art. 26 |
| Out of scope | 3 | "How long should pasta boil?" → none |

## Decisions

1. **Runner: Promptfoo.** Its HTTP provider calls `/api/search`, and assertions compute the metrics. Telemetry and update checks are switched off. F-06 to F-09 reuse it for the LLM judge and the model comparison.
2. **Corpus:** the AI Act and the GDPR in English and Polish from the Publications Office, pinned by SHA-256 and fetched by `make eval-corpus`, not committed.
3. **Expected sources** are written by location (document, article, paragraph) and resolved to chunk ids at run time; the report records the resolved ids.
4. **Targets:** the first run sets the baseline, and the gate fails on a drop of more than 5 points. Targets are proposed in an ADR after F-05.
5. **Runs locally** with `make eval`; a manual CI workflow follows in F-09.

ADR needed before the plan: Promptfoo as the evaluation runner and the evaluation corpus pinned by hash.
