# 0009. Test-first commits, kept in history

- Status: accepted
- Date: 2026-10-28
- Related: ADR 0006, [workflow.md](../workflow.md)

## Context

This repository is public from the first commit, and it is built with a coding agent. A reader should be able to see how the work was done, not only the result: that tests came before code, that each feature had a spec and a review, and where a human made the decisions.

## Decision

1. Each plan step is delivered as two commits on a feature branch:
   - **red**: `test(<scope>): ...` adds failing tests (or evaluation cases) that specify the step,
   - **green**: `feat(<scope>): ...` or `fix(<scope>): ...` makes them pass without changing the tests.
   An optional third `refactor(<scope>): ...` commit keeps the tests green.
2. Review findings are fixed the same way: a test that reproduces the finding, then the fix.
3. Red commits are allowed only on feature branches. `main` is always green.
4. Pull requests are merged with a merge commit (`--no-ff`). No squash, no rebase-merge, so the red/green sequence and the feature boundary both stay visible.
5. CI runs on the pull request head and on `main`. Intermediate red commits are expected to fail tests and are not checked individually.
6. Git `pre-commit` hooks run formatting, linting and type checks only, never the test suite, so a red commit is possible.
7. Commits made with the coding agent carry a `Co-Authored-By` trailer. Commits reference the feature with a `Refs: F-xx` trailer.

## Alternatives considered

- **Squash merge** – a clean `main`, but erases the evidence of test-first work.
- **Single commit per step (test + code)** – cannot be told apart from tests written after the code.
- **Marking red tests `xfail`** – keeps every commit green, but adds noise and an extra commit to remove the marker.

## Consequences

- Good: `git log` of any feature shows spec → red → green → review fixes → docs.
- Good: an agent cannot quietly weaken a test to pass it; the green commit's diff must not touch test files (enforced by a hook during the green phase, see [workflow.md](../workflow.md)).
- Bad: more commits and a less linear `main`. Acceptable for a project whose history is part of the deliverable.
