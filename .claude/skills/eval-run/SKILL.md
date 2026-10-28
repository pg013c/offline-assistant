---
name: eval-run
description: Run the evaluation suite against the configured model(s), compare with the last baseline, and record the result. Use after any change to prompts, tool schemas, retrieval or model choice, and before review of such a feature.
argument-hint: [F-xx] [--models a,b] [--suite retrieval|answers|all]
---

# /eval-run

Evaluate model behaviour ([ADR 0006](../../../docs/adr/0006-tdd-for-code-evals-for-model-behaviour.md)). Code is checked by tests; this checks what the model does.

## Steps

1. Check the preconditions: the model server answers at the configured base URL, the models named in configuration are available, the index is built for the evaluation dataset. If not, say what is missing and stop; do not download anything without the human's go-ahead.
2. Run `make eval` (or the suite or models passed as arguments). Comparison with Claude needs `ASSISTANT_ALLOW_NETWORK=1`; ask before enabling it.
3. Read the results and compare with the last baseline in `docs/evals/`. For each metric in the PRD quality targets report: value, target, change from baseline.
4. If any metric is below target or dropped by more than 5 points, run the `eval-analyst` agent on the failing cases and include its explanation.
5. Record the outcome:
   - during a feature: a section in `docs/features/F-xx-*/review.md` (create it if needed) with the metrics table,
   - when the run sets a new baseline or compares models: a new file `docs/evals/YYYY-MM-DD-<topic>.md` with model versions, hardware, configuration, dataset version and metrics (AI-61).
6. Commit the record: `docs(eval): <topic>` with trailers. Raw result files stay out of git unless they are the published comparison.

## Rules

- Never edit evaluation cases to make a run pass. A case that is wrong is fixed in its own `test(eval): ...` commit with the reason.
- Report numbers, not impressions. Say how many cases a metric is based on.
