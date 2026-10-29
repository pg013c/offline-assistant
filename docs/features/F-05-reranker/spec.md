# F-05. Reranker

- Status: approved
- Requirements: FR-06, FR-43; AI-31, AI-61; NFR-03
- Related ADRs: 0002, 0004, 0006, 0016, 0017, 0018

## Why

Hybrid search (F-03, F-04a) puts every expected passage in the top 10, but two exact-reference cases still rank 8 and 9: passages that cite "Article 83" or "Annex III" outrank the article or annex itself, because dense and BM25 scores look at the question and the passage separately. A cross-encoder reads the question and the passage together and is the usual fix (FR-06). The PRD asks for it to be switchable, so the evaluation can show what it adds and what it costs (FR-43).

## Scope

- **Reranking:** questions and searches take a wider set of hybrid-search candidates, a local multilingual cross-encoder scores each question–passage pair, and the passages are returned in the reranker's order.
- **Switch:** reranking is on or off by configuration, and a search request can ask for either, so one index serves both measurements.
- **Model:** pinned by revision and checked by hash like the other models, fetched by `make models`, loaded offline (ADR 0004, 0016).
- **Measuring:** `make eval` scores retrieval with and without the reranker on the same index, and records the search latency of both. The report also records the highest similarity reached by an out-of-scope question (F-04a review #7).
- **Refusal:** whether a question is answered still depends on the dense similarity threshold (0.5), not on the reranker score.

## Out of scope

- Using the reranker score as the refusal threshold: decided on measurements, after this feature, with the targets ADR.
- Retrieval targets: proposed in an ADR after this feature, as ADR 0018 says.
- Reranking for the agent's tool calls: F-07 uses the same search, so it gets reranking without extra work.
- Changes to the evaluation dataset.

## Acceptance criteria

- [x] AC-1: Given candidates from hybrid search, when reranking is on, then passages come back in the order of the reranker's score, ties broken by the hybrid order, and the response says reranking was used. Proof: `tests/unit/domain/test_rerank.py`; `tests/unit/services/test_question_service.py::test_with_a_reranker_search_returns_the_rerankers_order_and_scores`, `::test_equal_reranker_scores_keep_the_index_order`; `tests/unit/api/test_search_api.py::test_with_a_reranker_hits_are_reranked_and_carry_its_score` (`rerank_score`).
- [x] AC-2: Given reranking is off by configuration or by the request, then the order is exactly the hybrid order of F-04a. Proof: `test_question_service.py::test_without_reranking_search_returns_the_index_order_unscored`, `::test_without_a_reranker_the_default_is_the_index_order`; `test_search_api.py::test_a_search_can_ask_for_the_hybrid_order`; `make eval` hybrid mode equals the F-04a figures.
- [x] AC-3: Given the reranker model is missing or its files fail their hash, when the API starts with reranking on, then it refuses to start with `ModelsNotReady`, naming the model; with reranking off it starts. Proof: `tests/integration/test_app_startup.py::test_a_missing_reranker_stops_the_app_naming_it`, `::test_with_reranking_off_the_app_starts_without_the_reranker`; `tests/unit/test_settings.py::test_with_reranking_on_a_missing_reranker_stops_startup`; hash checks in `tests/unit/adapters/test_pinned_models.py`.
- [x] AC-4: Given an out-of-scope question, when reranking is on, then no passage is used for an answer (the dense threshold still decides). Proof: `test_question_service.py::test_the_dense_threshold_still_refuses_what_the_reranker_scores_high`, `::test_with_a_reranker_answers_use_only_its_top_ten_like_the_evaluation`; `make eval`: out-of-scope refused 3/3 with the reranker, top similarity 0.38.
- [x] AC-5: Given the evaluation corpus, when `make eval` runs, then the report holds recall@3, recall@10, MRR, the refusal shares and the median and 95th-percentile search latency for both modes, plus the highest out-of-scope similarity; the gate compares the default mode against the baseline. Proof: `evals/tests/test_report.py`, `test_metrics.py`, `test_promptfoo.py`, `test_run.py` (integration); report `retrieval-20261029T160557Z.json`.
- [x] AC-6: The result with and without the reranker is recorded in `docs/evals/`, and the default mode is the one the recorded result supports (decision 4). Proof: [record](../../evals/2026-10-29-retrieval-reranker.md): recall@3 and MRR higher, no metric worse, p95 473 ms; `ASSISTANT_RERANKER` defaults to `on` (`test_settings.py::test_reranking_is_on_by_default`).

## Evaluation cases

The F-04 suite (dataset version 2, 24 cases) runs unchanged in both modes. The cases this feature targets:

| Id | Input | Expected |
|---|---|---|
| ref-article-83 | What does Article 83 of the GDPR set out? | GDPR (EN) Art. 83 in the top 3 (now rank 8) |
| ref-annex-iii | What does Annex III of the AI Act list? | the Annex III passages in the top 3 (now rank 9) |
| x-pl-to-en-breach, x-en-to-pl-erasure | cross-language questions | no worse than without the reranker |
| oos-pasta, oos-world-cup, oos-weather-krakow | out-of-scope questions | still refused |

## Decisions

1. **Model:** `BAAI/bge-reranker-v2-m3` (Apache-2.0, multilingual, built on the same XLM-RoBERTa base as BGE-M3), run with the sentence-transformers library already in the backend. A new model needs an ADR (`/adr`).
2. **Candidates:** the reranker scores the top 30 hybrid candidates; answers keep the best 3 above the threshold, searches return the requested limit.
3. **Switch:** `ASSISTANT_RERANKER` (`on` by default, `off`), and an optional `rerank` field on `POST /api/search` for the evaluation.
4. **Default:** the reranker is on by default only if, with it, recall@3 and MRR are higher, no metric is more than 5 points worse, and the 95th-percentile search latency stays under 1 s on the reference hardware. Otherwise it ships switched off and the record says why.

## Open questions

None. The human confirmed the decisions above on 2026-10-29. Decision 1 is recorded with `/adr` before the plan.
