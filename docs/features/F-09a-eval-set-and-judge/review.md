# F-09a. Review

- Reviewed range: `main..feat/F-09a-eval-set-and-judge` at `85127ef`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-30-answers-judged.md](../../evals/2026-10-30-answers-judged.md). The gate fails on calibration: correctness agreement is 80 %, support agreement 85.7 %, and the bar is 85 %.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

All 15 findings were confirmed against the code; none was dropped.

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | blocker | `Makefile:73-75` | The green commit for the thinking judge also removed `--reasoning-budget 0` from `make llm`, so the default model would be served with thinking on. No test pins it. The measurements are not affected: the 8B server in use was started before the change, with thinking off. | ADR 0021, ADR 0009, CLAUDE.md rule 6 | |
| 2 | major | `docs/evals/answer-baseline.json`, the record | A run that failed its calibration gate became the baseline, and its `judged_correct` (64.6 %) is named as F-09b's comparison number, although the spec says a judge below the bar is not used. | AC-3, AC-7, ADR 0022 §3 | |
| 3 | major | `evals/harness/run.py:481-483`, `answers.py:384-405` | Answers that failed or did not complete are left out of `judged_correct` instead of counting as wrong. "Not judged" mixes a judge failure with a model failure. | AC-2, AC-4 | |
| 4 | major | `evals/harness/answers.py:440-495` | The per-case report lacks citation support and tool-call validity, and the Markdown case table has none of the three judged measures. | AC-4 | |
| 5 | major | `evals/harness/run.py:230` | The judge's identity is only a name and URL. The llama.cpp build, model file, thinking setting, token budget and prompt hash are not recorded. | AC-7, AI-61, TEST-23 | |
| 6 | major | `evals/harness/judge.py:106`, `run.py:483,493` | A verdict that exceeds the 600 s timeout raises `JudgeUnavailable`, which nothing catches. The run then dies without a report. | AC-2, AC-6 | |
| 7 | minor | `evals/harness/run.py:464-493, 276-278` | No tests for `judge_answers`, `calibrate`, the "start it with make judge" note, or calibration failures in the run's failures. | TEST-09, AC-3, AC-6 | |
| 8 | minor | `evals/harness/run.py:487-490` | A missing `calibration.yaml` turns the calibration gate off silently. | AC-3, ADR 0022 §3 | |
| 9 | minor | `scripts/ci/test-make.sh:72-74` | The "judge thinks" check passes when `make -n judge` prints nothing. | TEST-09 | |
| 10 | minor | `evals/harness/judge.py:117-124` | The answer and passages, injected documents included, reach the judge without delimiters. | AI-10 | |
| 11 | minor | `evals/harness/calibration.py:66-68` | Calibration parses citation markers with its own regex, not the one `answers.py` uses. | | |
| 12 | minor | `docs/backlog.md` | The record's findings (correctness agreement below the bar, citation-support work) have no backlog rows. | | |
| 13 | note | `evals/datasets/calibration.yaml` (`d68485e`) | All five label corrections moved toward the judge after its disagreements were seen. The other 30 support labels were not re-checked against the full passages. | | |
| 14 | note | `spec.md:21` | The spec says two to four key points; the plan, dataset and tests allow one (for injection cases). | | |
| 15 | note | commit `cb433f0` | The dataset commit also carries a two-line harness stub. | TEST-22 | |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
