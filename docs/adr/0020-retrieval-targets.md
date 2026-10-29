# 0020. Retrieval targets: floors that `make eval` enforces

- Status: accepted
- Date: 2026-10-29
- Related: PRD §9, AI-31, FR-43, NFR-03, F-04, F-05, ADR 0006, ADR 0018

## Context

ADR 0018 left retrieval targets to an ADR after the reranker (F-05). Today `make eval` only guards against regression: no metric may drop more than 5 points from the recorded baseline (PRD §9). That has two gaps:

- **Drift.** A run 4 points worse becomes the next baseline, and the next drop is measured from there, so quality can fall without limit in small steps.
- **No definition of "good enough."** F-06 to F-09 change what feeds the answer (the agent, the models) and need a fixed floor to be judged against, not only the last run.

The measured baseline (F-05, [record](../evals/2026-10-29-retrieval-reranker.md); dataset version 2: 21 in-scope and 3 out-of-scope cases; reference Mac):

| Metric | Reranked (default) | Hybrid |
|---|---|---|
| recall@3 | 95.2 % (20 of 21) | 90.5 % |
| recall@10 | 100 % | 100 % |
| MRR | 0.873 | 0.821 |
| answerable@3 | 90.5 % (19 of 21) | 90.5 % |
| out-of-scope refused | 100 % (3 of 3), top similarity 0.38 | 100 % |
| in-scope unanswered | 0 % | 0 % |
| search latency p95 | 473 ms | 30 ms |

One in-scope case is 4.8 points and one out-of-scope case is 33 points, so a floor equal to today's value would fail on a single case changing rank. The dataset grows in F-09.

## Decision

1. **Floors for the default mode**, checked by `make eval` in addition to the 5-point regression gate. A run below any floor fails, whatever the baseline says.

   | Metric | Floor | Today | Room |
   |---|---|---|---|
   | answerable@3 | ≥ 85 % | 90.5 % | 1 case |
   | recall@3 | ≥ 85 % | 95.2 % | 2 cases |
   | recall@10 | ≥ 95 % | 100 % | 1 case |
   | MRR | ≥ 0.75 | 0.873 | |
   | out-of-scope refused | ≥ 90 % (PRD §9) | 100 % | none with 3 cases |
   | in-scope unanswered | ≤ 5 % | 0 % | 1 case |

2. **answerable@3 is the headline.** It counts what an answer can use: an expected chunk among the first three hits at or above the threshold. recall@3 and MRR describe search order.
3. **Latency is a target, not a gate.** The p95 search latency of the default mode should stay under 1 s on the reference Mac (F-05 decision 4, part of NFR-03's 3 s budget). It is reported by every run and compared in reviews, because it depends on the machine that runs `make eval`.
4. **Floors are revised in F-09**, when the dataset grows, by a new ADR. Until then a floor changes only through a superseding ADR.

## Alternatives considered

- **Regression gate only (today)** – no fixed bar. Quality can drift down 4 points at a time, and later features have nothing absolute to meet.
- **Floors equal to today's values** – any single case changing rank fails the run. With 21 cases that is noise, not a regression.
- **Targets from published benchmarks** – numbers from other datasets say nothing about this corpus and these questions.
- **Gate latency too** – `make eval` runs on whatever machine a developer has. A gate that fails on a slower laptop would be switched off, not trusted.

## Consequences

- **Good:**
  - a fixed bar for F-06 to F-09;
  - drift below it is caught;
  - the floors leave room for one case changing.
- **Bad:**
  - with 3 out-of-scope cases, the refusal floor allows no miss at all until F-09 adds cases;
  - floors on 21 cases are coarse.
- **Follow-up:**
  - `evals/harness/gate.py` checks the floors (a `chore` with tests);
  - the floors are listed in `docs/standards/testing.md` (TEST-24);
  - F-09 revisits them with the full evaluation set.
