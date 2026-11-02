# 0025. Judge answers with Gemma 4 26B-A4B, thinking off

- Status: accepted
- Date: 2026-11-02
- Related: F-09b, F-09c, TEST-24, ADR 0022, ADR 0023, ADR 0024
- Amends: ADR 0022, decision 1 (the judge model). Supersedes: ADR 0023 (thinking on)

## Context

On llama.cpp 0.8.0 (ADR 0024), Qwen3 30B-A3B with thinking on agrees with the hand verdicts on 81.2 % of correctness verdicts, below the 85 % bar of ADR 0022. All five F-09b runs fail calibration with the same 15 disagreements.

- **Too lenient:** it credits key points the answer leaves out, as in cal-01, cal-13, cal-19 and cal-32.
- **Off-topic answers pass:** cal-46 and cal-47 answer another question, and it rules them correct or partial.
- **The labels hold:** they were reviewed on 2026-11-02 and are unchanged.

**A spike on 2026-11-02** ran only the calibration set (48 items, 74 cited sentences) on each setup. The harness, prompt, JSON schema, temperature 0 and 8192 tokens were the same throughout, and so were the flags of `make judge`.

| Judge | Correctness | Support | Time | Notes |
|---|---|---|---|---|
| Qwen3 30B-A3B, thinking on (now) | 81.2 % | 91.9 % | 7 min | repeats the step-9 runs exactly |
| Qwen3.6 35B-A3B, thinking on | 93.8 % | 97.3 % | 40 min | ~3,800 reasoning tokens per verdict |
| Qwen3.6 35B-A3B, thinking off | 95.8 % | 87.8 % | 2.3 min | too strict on support: 8 sentences |
| Gemma 4 26B-A4B, thinking on | 66.7 % | 64.9 % | 90 min | 13 items use all 8192 tokens and get no verdict |
| **Gemma 4 26B-A4B, thinking off** | **97.9 %** | **95.9 %** | **1.9 min** | the same verdicts on a second run |

**Where Gemma 4 with thinking off still disagrees with the labels:**

- cal-01: it rules correct where the label says partial;
- three sentences are labelled unsupported but it rules them supported: cal-02 S1, cal-04 S1 and cal-12 S1. All three are known borderline cases.

It rules cal-46 and cal-47 wrong, as the labels do.

Both models are already pinned as F-09b candidates (ADR 0024) and are Apache-2.0 and offline. Gemma 4 is 14.4 GB.

## Decision

1. **Judge model:** Gemma 4 26B-A4B. It uses the file ADR 0024 pins, `gemma-4-26B_q4_0-it.gguf`, SHA-256 `3eca3b8f…eca51d`.
2. **Thinking off:** `make judge` serves it with `--reasoning off` and the flags `make llm` uses. The harness records `thinking: false`.
3. **The rest of ADR 0022 stands:** the prompt, the 85 % bar for correctness and for support, the answer floors and calibration on every judged run.
4. **Self-judging check:** Gemma 4 is also a candidate, so its own answers are judged a second time. Qwen3.6 35B-A3B with thinking off, which passes the bar, re-judges them.
   - The record reports both verdicts for Gemma 4.
   - If the two differ by more than 5 points of judged correctness, the record says so. Gemma 4 then cannot win the selection on judged correctness alone.
5. **Qwen3 30B-A3B leaves:** it leaves the judge pins and `make judge-models`, and 18.6 GB less is fetched.

## Alternatives considered

- **Qwen3.6 35B-A3B, thinking on:**
  - it passes the bar comfortably;
  - but calibration alone takes 40 minutes, and a judged run takes about 1.5 hours;
  - it shares a family with three of the five candidates.
- **Qwen3.6 35B-A3B, thinking off:**
  - it is fast and passes;
  - but support at 87.8 % is close to the bar;
  - it shares a family with three of the five candidates, so it is kept for the check in decision 4.
- **Keep Qwen3 30B-A3B, tune the prompt or relabel:**
  - ADR 0023 found that prompt tuning did not move its leniency;
  - relabelling to fit the judge is what calibration exists to prevent.
- **Lower the bar:** it would report numbers from a judge that passes off-topic answers.
- **Claude as the judge:** it needs network mode and money on every run. It stays F-09c's cross-check.

## Consequences

- **Good:**
  - calibration passes with a margin;
  - a judged run gets faster, since calibration drops from 7 minutes to 2;
  - the judge is outside the Qwen family, so same-family bias no longer applies to four of the five candidates or to the current default.
- **Bad:**
  - the judge was chosen on the same 48 items that gate it, so its agreement on new answers may be lower. F-09c's Claude re-judging measures that;
  - Gemma 4 judges its own answers, which decision 4 checks.
- **Follow-up:**
  - an F-09b plan step, done test first:
    - `JUDGE_MODELS` becomes the Gemma 4 pin;
    - the judge identity changes: the alias, `thinking: false` and `JUDGE_MODEL`;
    - the `make judge` flags change;
    - the step 9 runs are re-judged, and Gemma 4's runs also get the second judge.
  - The judge's pin outlives the choice of default even if Gemma 4 is not kept as a candidate (ADR 0024, decision 5).
  - The README judge sentence and the licence table name the new judge.
