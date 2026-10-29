# F-05. Review

- Reviewed range: `main...feat/F-05-reranker` at `1b1aa4d`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-29-retrieval-reranker.md](../../evals/2026-10-29-retrieval-reranker.md). Against the hybrid order: recall@3 90.5 → 95.2 %, MRR 0.821 → 0.873, p95 search latency 31 → 498 ms, out-of-scope refusals 3/3.
- Checks: `make check` passes. Red commits precede green ones, and no green commit touches a test.
- Verification: all 9 findings confirmed against the code and the raw results (`retrieval-20261029T151435Z.json`, `promptfoo-20261029T151435Z.json`); none dropped.
  - **Finding 1, answer level:** counting a case as answered when an expected chunk is among the first 3 hits at or above the threshold, both modes answer 19 of 21 cases.
  - **Finding 3:** the first reranked request took 3295 ms; the others took about 400 ms.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `evals/harness/metrics.py:68`, the evaluation record | The recall@3 gain is one case, `ref-article-83`. Its expected chunk ranks first with dense similarity 0.46, below the 0.5 threshold, so an answer cannot use it. The metrics measure search order, not what an answer can use, and do not flag this. | spec decision 4, AC-6, AI-31 | fix: add `answerable@3` (an expected chunk among the first 3 hits at or above the threshold) for both modes, gated; restate the record; measure again |
| 2 | major | `services/questions.py:92`, `evals/promptfoo/retrieval.yaml` | With the reranker, answers apply the threshold to 30 candidates, but the evaluation sees only the top 10. An out-of-scope question with a passage at or above 0.5 at reranked ranks 11–30 would be answered, while the refusal share and top out-of-scope similarity say otherwise. | AC-4, AC-5 | fix: answers use the reranker's top 10 in both modes, the pool the evaluation sees |
| 3 | major | `evals/harness/run.py`, `metrics.py:120`, the evaluation record | The reranker loads on the first request (3.3 s), which is counted as a search. The p95 of 24 values is the second-largest, so it leaves the cold load out only by luck of the case count. The cold start of the default mode is not reported. | AC-5, spec decision 4 | fix: the API loads the reranker at startup; the harness sends one unmeasured request per mode and reports the cold start separately |
| 4 | minor | `spec.md:42`, the evaluation record | The spec expects `ref-annex-iii` in the top 3; it ends at rank 6. The record explains it and moves it to F-09, but no human decision is recorded. | plan step 6 | fix: record the human's acceptance (2026-10-29); the case moves to F-09 |
| 5 | minor | `evals/harness/run.py:192-203` | The evaluation API does not set `ASSISTANT_RERANKER=on`. If the default were `off`, the reranked provider would get 409 and `make eval` would fail. | AC-5 | fix |
| 6 | minor | `evals/harness/run.py:357-361` | The run metadata does not record the candidate count, the reranker's device or its precision; the float32 and float16 runs differ only in the commit. | AI-61 | fix |
| 7 | minor | `tests/unit/test_settings.py`, `app.py` | AC-3 is tested through `reranker_for` only. Removing the call from `build_adapters` would keep every test green, and a missing model would fail on the first question instead of at startup. | AC-3, TEST-09 | fix |
| 8 | note | commit `2152e76` | The removed Article 83 test is consistent with finding 1, and the record does not mention it. | – | fix |
| 9 | note | `services/questions.py:92`, `architecture.md` | Turning the reranker on also widens the pool the threshold is applied to, from 10 to 30. `architecture.md` does not say so. | – | fix (by finding 2) |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
