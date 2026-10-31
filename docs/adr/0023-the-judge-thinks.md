# 0023. The judge thinks before it rules

- Status: accepted
- Date: 2026-10-30
- Related: F-09a, TEST-24, ADR 0022
- Amends: ADR 0022, decision 2 ("thinking off")

## Context

ADR 0022 serves the judge with thinking off and fails a run when the judge agrees with the hand verdicts of the calibration set on less than 85 % of correctness or support verdicts.

**Measured on the 20 calibration items** (35 cited sentences), Qwen3 30B-A3B at temperature 0:

| Judge | Correctness | Support | Time per answer |
|---|---|---|---|
| One overall verdict, thinking off | 55 % | 91 % | ~3 s |
| A verdict per key point, thinking off | 55 % | 74 % | ~3 s |
| A verdict per key point with a quote from the answer, thinking off | 55 % | 71 % | ~3 s |
| A verdict per key point, thinking on | 75 % | 80 % | ~12 s |

**Why thinking off fails:** the judge credits key points the answer does not make. For example, it accepts "up to 4 % of turnover" for an answer that gives only EUR 20 million. Asking it to quote the answer did not help.

## Decision

1. **Thinking on:** `make judge` serves the judge with thinking on, with llama-server's default reasoning budget instead of `--reasoning-budget 0`.
2. **Room to think:** the harness gives each verdict room for its reasoning: up to 8192 tokens and 10 minutes per request.
3. **The rest of ADR 0022 stands:** the model, its pin, the 85 % calibration bar and the answer floors.

## Alternatives considered

- **Keep thinking off and tune the prompt:**
  - three prompt shapes left correctness at 55 %;
  - the leniency did not move.
- **A larger judge:**
  - Qwen3 32B dense is about four times slower per token, and it is another 20 GB download;
  - thinking costs less and was measured to help.
- **Lower the bar:**
  - a judge that agrees with the human on 55–75 % of verdicts gives numbers nobody can trust;
  - that is what the bar exists to stop.

## Consequences

- **Good:**
  - calibration agreement rises from 55 % to 75 % on correctness before any prompt tuning;
  - the judge's verdicts become explainable from its reasoning.
- **Bad:**
  - a judged run takes about four times longer: roughly 10 minutes for the answer suite, plus 4 for calibration;
  - reasoning varies more than a direct reply, even at temperature 0, which the calibration measures each run.
- **Follow-up:**
  - prompt tuning against the calibration set, in F-09a;
  - if the bar is still not met, the shortfall is recorded as a finding in the F-09a record.
