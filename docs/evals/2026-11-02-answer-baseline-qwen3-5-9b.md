# Answer baseline of Qwen3.5 9B, 2026-11-02

The default model chosen by ADR 0026, measured on the commit that makes it the default (`a7a0e6f`). Report `answers-qwen3.5-9b-20261102T192244Z.json` replaces Qwen3 8B's report of 2026-10-30 in `answer-baseline.json`. From now on, every answer run of the default is held to it under the 5-point rule (TEST-24).

## Setup

The setup is the same as in the [model comparison](2026-11-02-model-comparison.md):

- llama.cpp `b11960-8642541b2`, with `make llm` serving `qwen3.5-9b` on port 8080 and thinking off;
- the Gemma 4 judge from `make judge` on port 8081 (ADR 0025);
- `answers.yaml` version 5, with 47 cases, 41 of them to answer;
- `calibration.yaml` version 2;
- an Apple M5 Pro with 64 GB.

## Results

| Metric | Baseline | Comparison run (`…T141748Z`) | Cases | Target or floor |
|---|---|---|---|---|
| `judged_correct` (partial counts half) | 81.7 % | 81.7 % | 41 | ≥ 75 % (ADR 0026) |
| `citation_support` | 97.7 % | 97.7 % | 129 sentences | ≥ 90 % |
| `tool_call_validity` | 100 % | 100 % | 13 tool turns | ≥ 95 % |
| `out_of_scope_refused` | 100 % | 100 % | 3 | ≥ 90 % |
| `cites_expected` | 95.1 % | 95.1 % | 41 | |
| `language_match` | 100 % | 100 % | 41 | |
| `valid_first_try` | 63.4 % | 63.4 % | 41 | |
| `answer_failed` | 0 % | 0 % | 41 | |
| `expected_tools_used` | 71.4 % | 71.4 % | 7 | |
| `notes_saved_when_asked` | 33.3 % | 33.3 % | 3 | |
| `notes_saved_unasked`, `injection_followed` | 0 % | 0 % | 44, 6 | |
| `not_covered_correct` | 66.7 % | 66.7 % | 3 | |
| First token, median | 1.15 s | 1.14 s | | ≤ 2 s (NFR-03) |
| First token, 95th percentile | 11.8 s | 11.7 s | | ≤ 15 s (NFR-03) |
| Tokens per second, median | 46 | 44 | | |
| Peak memory | 15 786 MiB | 15 785 MiB | | 24 GiB |
| Calibration, correctness / support | 97.9 / 95.9 % | 97.9 / 95.9 % | 48 / 74 | 85 % |

**The run passes its gate.** It meets every floor, the 75 % correctness target and both NFR-03 limits. It was held to the floors only, because the previous baseline was of another model.

## Findings

1. **The run repeats the comparison run exactly:**
   - every quality metric is the same;
   - every case gets the same correctness verdict;
   - the calibration disagreements are the same 4 items.

   At temperature 0, with thinking off for both the model and the judge, the suite is reproducible on this build. Timing varies by about 1 %.
2. **The margins are thin in two places.**
   - Judged correctness is 6.7 points above its target.
   - The 95th-percentile first token is 3.2 s under its limit. It comes from the agent path and from the retries of 37 % of answers, which are invalid on the first try.
3. **The weaknesses are known and in the backlog:**
   - first-try validity of structured answers;
   - note saving, at 1 of 3 requests. Its integration test is marked as expected to fail;
   - use of the expected tools;
   - not-covered answers.
