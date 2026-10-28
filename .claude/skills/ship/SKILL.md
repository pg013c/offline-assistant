---
name: ship
description: Finish a feature branch - verify every acceptance criterion against its proof, update architecture, ADR index, backlog and README, push the branch and open a pull request for the human to merge. Use after review findings are resolved.
argument-hint: F-xx
---

# /ship F-xx

## Steps

1. Check the definition of done in `docs/workflow.md` §6. Run `make check`; for model-behaviour features confirm the last `/eval-run` passed; run `make offline-check` if it exists.
2. For each acceptance criterion in `spec.md`, find the test or evaluation case that proves it and run it. Tick the criterion and write the pointer next to it. An unproven criterion stops the ship.
3. Confirm every finding in `review.md` has a decision and every `fix` has its commits listed.
4. Update the documents the feature affected:
   - `docs/architecture.md` if structure, flows or deployment changed,
   - `docs/adr/README.md` index,
   - `docs/backlog.md` status `done`,
   - `README.md` if setup, usage, models or results changed.
   Commit: `docs(F-xx): update docs for release` with trailers.
5. Ask the human before pushing. Then push the branch and open a pull request with `gh pr create` using `.github/pull_request_template.md`: summary, links to spec, plan and review, evaluation result, decisions the human made, and how to try it.
6. Report the PR link. Do not merge; the human merges with a merge commit (ADR 0009).
