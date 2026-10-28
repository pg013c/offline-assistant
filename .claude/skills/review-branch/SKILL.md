---
name: review-branch
description: Review everything the current branch changes against the spec, plan and engineering standards, using the reviewer agent with a fresh context, and write findings to review.md for the human to triage. Use when a feature's plan steps are done, and for every fix or chore branch.
argument-hint: [F-xx]
---

# /review-branch [F-xx]

## Steps

1. Determine the range: `main...HEAD`. If the branch has uncommitted changes, stop and ask to commit or stash them first.
2. Run `make check` first. A failing check is reported as a blocker without a full review.
3. Start the `reviewer` agent. Give it only: the branch range, the paths to `spec.md`, `plan.md`, `docs/standards/`, the relevant ADRs, and the evaluation result if there is one. Do not give it your own opinion of the change or the history of how it was built; its value is that it has not seen either.
4. Verify each finding the agent returns: open the cited lines and confirm the problem is real. Drop findings you cannot confirm and say how many you dropped.
5. Write `docs/features/F-xx-*/review.md` from [the template](../../../docs/features/_templates/review.md), findings ordered by severity, each citing a standard id or an acceptance criterion where one applies. Leave the Decision column empty.
6. Set backlog status to `review`. Commit `docs(F-xx): add review` with trailers.
7. Present the findings to the human and ask for a decision per finding: `fix`, `backlog`, or `reject: <reason>`. Record the decisions in `review.md`.
8. Findings marked `fix` are implemented with `/tdd` (one per invocation). When all are resolved, suggest `/ship`.

For a branch without a feature folder (fix, chore), skip the file and present the findings in the conversation.
