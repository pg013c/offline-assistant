# F-09a. Review

- Reviewed range: `main..feat/F-09a-eval-set-and-judge` at `85127ef`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-30-answers-judged.md](../../evals/2026-10-30-answers-judged.md). The gate fails on calibration: correctness agreement is 80 %, support agreement 85.7 %, and the bar is 85 %.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

All 15 findings were confirmed against the code; none was dropped.

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | blocker | `Makefile:73-75` | The green commit for the thinking judge also removed `--reasoning-budget 0` from `make llm`, so the default model would be served with thinking on. No test pins it. The measurements are not affected: the 8B server in use was started before the change, with thinking off. | ADR 0021, ADR 0009, CLAUDE.md rule 6 | fix |
| 2 | major | `docs/evals/answer-baseline.json`, the record | A run that failed its calibration gate became the baseline, and its `judged_correct` (64.6 %) is named as F-09b's comparison number, although the spec says a judge below the bar is not used. | AC-3, AC-7, ADR 0022 §3 | fix |
| 3 | major | `evals/harness/run.py:481-483`, `answers.py:384-405` | Answers that failed or did not complete are left out of `judged_correct` instead of counting as wrong. "Not judged" mixes a judge failure with a model failure. | AC-2, AC-4 | fix |
| 4 | major | `evals/harness/answers.py:440-495` | The per-case report lacks citation support and tool-call validity, and the Markdown case table has none of the three judged measures. | AC-4 | fix |
| 5 | major | `evals/harness/run.py:230` | The judge's identity is only a name and URL. The llama.cpp build, model file, thinking setting, token budget and prompt hash are not recorded. | AC-7, AI-61, TEST-23 | fix |
| 6 | major | `evals/harness/judge.py:106`, `run.py:483,493` | A verdict that exceeds the 600 s timeout raises `JudgeUnavailable`, which nothing catches. The run then dies without a report. | AC-2, AC-6 | fix |
| 7 | minor | `evals/harness/run.py:464-493, 276-278` | No tests for `judge_answers`, `calibrate`, the "start it with make judge" note, or calibration failures in the run's failures. | TEST-09, AC-3, AC-6 | fix |
| 8 | minor | `evals/harness/run.py:487-490` | A missing `calibration.yaml` turns the calibration gate off silently. | AC-3, ADR 0022 §3 | fix |
| 9 | minor | `scripts/ci/test-make.sh:72-74` | The "judge thinks" check passes when `make -n judge` prints nothing. | TEST-09 | fix |
| 10 | minor | `evals/harness/judge.py:117-124` | The answer and passages, injected documents included, reach the judge without delimiters. | AI-10 | fix |
| 11 | minor | `evals/harness/calibration.py:66-68` | Calibration parses citation markers with its own regex, not the one `answers.py` uses. | | fix |
| 12 | minor | `docs/backlog.md` | The record's findings (correctness agreement below the bar, citation-support work) have no backlog rows. | | fix |
| 13 | note | `evals/datasets/calibration.yaml` (`d68485e`) | All five label corrections moved toward the judge after its disagreements were seen. The other 30 support labels were not re-checked against the full passages. | | fix |
| 14 | note | `spec.md:21` | The spec says two to four key points; the plan, dataset and tests allow one (for injection cases). | | fix |
| 15 | note | commit `cb433f0` | The dataset commit also carries a two-line harness stub. | TEST-22 | reject: the history is committed, and the stub is a two-line harness change, not code under evaluation |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1, 9 | `6677ce0` test, `5c6460a` fix |
| 3, 6 | `c2f8762` test, `d6f76e9` fix |
| 2, 7, 8 | `e1252cf` test, `e894bd9` fix |
| 4, 5 | `6cbbd5d` and `8ec44c2` test, `6bb45d1` fix |
| 10, 11 | `a302a03` test, `ff87ec7` fix |
| 12, 14 | `52d1553` docs |
| 13 | The other 30 support labels were re-read against the full passages; none needed a change (recorded in the record) |

## Evaluation after the fixes

Report `answers-20261030T165457Z.json`, the new answer baseline:

| Measure | Value | Bar or floor |
|---|---|---|
| Calibration, correctness | 75.0 % (20 items) | 85 %, fails |
| Calibration, support | 91.4 % (35 sentences) | 85 % |
| `judged_correct` | 68.3 %, untrusted | regression rule only |
| `citation_support` | 98.4 %, untrusted | 90 % |
| `tool_call_validity` | 100 % (16 tool turns) | 95 % |
| `cites_expected` | 90.2 % (41) | regression rule |

AC-3 is not proved while the judge is below the bar on correctness; raising it is in the backlog.

## Calibration on 48 items

The calibration set grew to 48 items (`6e69bb1`), all confirmed by the human. Report `answers-20261030T180237Z.json`, the new answer baseline, passes the gate:

| Measure | Value | Bar or floor |
|---|---|---|
| Calibration, correctness | 85.4 % (48 items) | 85 % |
| Calibration, support | 90.5 % (74 sentences) | 85 % |
| `judged_correct` | 68.3 % | regression rule only |
| `citation_support` | 100 % | 90 % |
| `tool_call_validity` | 100 % (16 tool turns) | 95 % |

AC-3 is proved. The margin is one item, and the judge is lenient on answers on another subject (cal-46); both are in the record and the backlog.
