---
name: tdd
description: Implement the next unchecked step of an approved plan (or one triaged review finding) as a red commit with failing tests and a green commit with the code that passes them. Use for all implementation work on a feature or fix branch.
argument-hint: F-xx [step number | finding number]
---

# /tdd F-xx [step]

Deliver one plan step, or one review finding marked `fix`, as a red/green commit pair. See `docs/workflow.md` §4 and ADR 0009.

The phase is tracked in `.claude/state/tdd-phase` (not committed). While it contains `green`, the `tdd-guard` hook rejects edits to tests and evaluation datasets.

## Red

1. Read `plan.md` and pick the step (default: first unchecked). For a review finding, read its row in `review.md`.
2. Confirm you are on the feature branch and the working tree is clean.
3. Run `mkdir -p .claude/state && echo red > .claude/state/tdd-phase`.
4. Write the tests the plan names for this step. Kind decides the form (`docs/standards/testing.md`):
   - `code`: unit tests with fakes, integration tests for real adapters, contract tests for new ports,
   - `eval`: evaluation cases in `evals/`,
   - `ui`: component or hook tests, or a Playwright journey,
   - `infra`: a check script or end-to-end assertion.
5. Add only the stubs needed for the tests to load: signatures that raise `NotImplementedError` (Python) or throw `new Error("not implemented")` (TypeScript). No logic.
6. Run the new tests. They must fail, and fail for the reason the step addresses (assertion or `NotImplementedError`), not because of an error in the test. Show the failure output.
7. Run formatting, lint and type checks (not the test suite) so the commit passes pre-commit.
8. Commit: `test(<scope>): <behaviour specified>` with `Refs: F-xx` and `Co-Authored-By`. Tick `red` in the plan in the same commit.

## Green

9. Run `echo green > .claude/state/tdd-phase`.
10. Implement the smallest change that makes the tests pass, following `docs/standards/`. Do not edit any test or dataset file. If a test is wrong, stop, explain, and with the human's agreement go back to step 3 with a separate `test(...)` commit that says why it changed.
11. If the step changed the API, run `make api-client`.
12. Run `make check`. Everything must pass, not only the new tests.
13. Commit: `feat(<scope>): ...` (or `fix(<scope>): ...` for findings and bugs) with trailers. Tick `green` in the plan in the same commit.
14. Optional: a `refactor(<scope>): ...` commit with tests unchanged and green.
15. Run `rm -f .claude/state/tdd-phase`.

## Then

- Report: step done, the two commit hashes, anything surprising.
- If the step was the last one, suggest `/eval-run` (when model behaviour changed) or `/review-branch`.
- Do one step per invocation unless the human asks for more.
