# F-07. Review

- Reviewed range: `main...feat/F-07-agent-with-tools` at `a737a16`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-30-answers-agent.md](../../evals/2026-10-30-answers-agent.md).
  - cites an expected passage 84.6 %;
  - language match 100 %;
  - valid on the first try 96.2 %;
  - out-of-scope refused 3/3;
  - injection followed 0/1;
  - not-covered correct 1/1;
  - time to first token 960 ms median, 6787 ms p95;
  - agent path 5.2 s median over 6 cases.
- Checks:
  - `make check` and `make eval-answers` pass;
  - the agent integration tests pass against Qwen3 8B;
  - commit rules pass.
- Decisions: by the human on 2026-10-30, as recommended.
- Verification:
  - all 15 findings confirmed against the code; none dropped;
  - findings 1 and 10 reproduced in Python;
  - finding 2 is a missing record: the results were reported to the human before this review, but no decision about them is written down;
  - finding 15 is also a missing record: the integration tests were run again after step 11 and passed, but that run is not recorded in the plan.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `domain/answers.py:201-203` | A number before a full stop never ends a sentence. So "…set out in Article 83. Fines reach 20 million euro [1]." is one statement, and the first sentence passes uncited. | AC-3, AI-01 || fix |
| 2 | major | `spec.md:14`, evaluation record | The final latency is not recorded as accepted: search-then-answer path 698 ms against F-06's 280 ms, agent path 5.2 s against NFR-03's 3 s. The spec says routing "keeps F-06's time to the first token". | plan step 9, NFR-03 || fix: the spec states the measured latency; the agent path's latency against NFR-03 is decided with F-09's models |
| 3 | major | `domain/answers.py:95-97`, `services/agent.py:83-108` | Research time sums model calls only. The gate search, reranking and tool runs are not counted, yet the record says the first token includes the whole research phase. | AI-60, AI-61 || fix: research is timed by a clock from the start of the question |
| 4 | minor | `domain/routing.py:11`, `services/tools.py:102-108` | Annex questions are routed to the tools, but `get_article` cannot read an annex: "III" is not a number, and annex chunks have no `article`. | spec decision 6 || fix: annexes leave the routing; reading an annex goes to the backlog (F-09) |
| 5 | minor | `services/agent.py:92-98` | Nothing caps the passages that reach the answer call. Several `get_article` or `compare` calls per turn can send dozens of chunks into a 16k context. | AI-22 || fix: at most 24 passages reach the answer |
| 6 | minor | `services/agent.py:86-88` | Tool-turn model calls are not logged per call. Their usage only goes into the summed end event. | AI-60, spec Measurement || fix |
| 7 | minor | `services/tools.py:107,120`, `services/agent.py:137` | `load_chunks` and `list_documents` read and decode files on the event loop. | – || fix |
| 8 | minor | `evals/harness/answers.py` (`_agent_scores`) | `citations_resolve` checks that cited ids are stored chunks, which is always true. The plan defined it as "returned in this run". | AC-7, plan step 8 || fix: the metric keeps its name so runs stay comparable, and is described as what it checks; unit tests prove citations come from the run |
| 9 | minor | `evals/datasets/answers.yaml` (`inj-cite-nothing`) | `injection_followed` scores only one case. Whether `inj-cite-nothing` obeyed its planted instruction is not an injection result. | AC-7, AI-12 || fix: an injection case that does not cite its expected source counts as followed |
| 10 | minor | `domain/routing.py:10-17` | Missed: "Art 17" (no dot) and "articles 5 and 6". Wrongly matched: "different retention periods". | spec decision 6 || fix |
| 11 | minor | `adapters/openai_compatible_chat.py:48` | A stale comment about passage tags now sits above `class LlmServer`. | – || fix |
| 12 | note | `plan.md:132` | Step 2's red box is unticked, though its red commit exists. | – || fix |
| 13 | note | `plan.md` | The criterion-to-proof mapping is in the plan. TEST-09 records it in `spec.md`. | TEST-09 || fix: moved at /ship |
| 14 | note | `services/agent.py:100-101` | A failed tool turn ends with `found=true`, as F-06's failures do. | – || reject: F-06 failures end the same way, and the error event already says there is no answer |
| 15 | note | `tests/integration/test_local_agent.py` | The run after decision 6 is not recorded, and the plan names `test_local_llm.py`. | – || fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `93ec272` test, `3b5794e` fix |
| 2 | docs commit (spec routing and decision 6 state the measured latency; evaluation record "After the review") |
| 3 | `59e262a` test, `f22a199` fix |
| 4 | `d59d43a` test, `9dc5d7a` fix; reading annexes is in the backlog for F-09 |
| 5 | `6960394` test, `9aefa1d` fix |
| 6 | `59e262a` test, `f22a199` fix |
| 7 | `6960394` test, `9aefa1d` fix |
| 8 | `7ce095a` fix (described in `_agent_scores`; the name stays so runs compare) |
| 9 | `95cc2d2` test, `7ce095a` fix |
| 10 | `d59d43a` test, `9dc5d7a` fix |
| 11 | `05b0c0d` refactor |
| 12 | docs commit (plan) |
| 13 | at /ship |
| 14 | rejected |
| 15 | docs commit (plan: file name and the runs after step 11 and the review) |
