# 0010. Continuous integration from the first commit

- Status: accepted
- Date: 2026-10-28
- Related: ADR 0004, ADR 0006, ADR 0009, [workflow.md](../workflow.md)

## Context

The repository is public and starts with documentation, standards and agent tooling before any application code. Rules written in documents are only as good as their enforcement: a commit convention nobody checks drifts, a hook nobody tests breaks silently, links rot as files move. The coding agent also needs a fast, objective signal that does not depend on its own judgement.

## Decision

GitHub Actions runs on every pull request and every push to `main`, from the first commit, in one workflow (`.github/workflows/ci.yml`). Checks grow with the code:

| Job | Checks | From |
|---|---|---|
| Docs | Markdown lint, spelling (typos), internal links and anchors (lychee, offline) | now |
| Tooling | workflow lint (actionlint), shell lint (shellcheck), agent settings are valid JSON, self-test of the agent hooks | now |
| Commit rules | Conventional Commit subjects; `feat`, `fix` and `refactor` commits do not touch tests or evaluation data (ADR 0009) | now |
| Backend | ruff, mypy, import contract, pytest (unit, contract, integration with service containers) | F-00 |
| Frontend | ESLint, Prettier, tsc, Vitest, Playwright, build | F-00 |
| API contract | regenerated TypeScript client matches the committed one (ADR 0005) | F-00 |
| Offline | stack started with networking disabled, end-to-end suite (ADR 0004) | F-10 |
| Evaluations | `make eval`, manual trigger only, needs a model server (ADR 0006) | F-04 |

Supply-chain and permission rules for the workflows themselves:

- Third-party actions are pinned to a full commit SHA with the version in a comment. Dependabot proposes updates weekly.
- The default token is read-only (`permissions: contents: read`); a job that needs more asks for it explicitly.
- Every job has a timeout.

`main` is protected: changes arrive through pull requests, and the CI jobs are required checks.

## Alternatives considered

- **Start CI with the first code (F-00)** – the documents, commit history and hooks written before it would never be checked, and the commit rules would start with exceptions.
- **pre-commit.ci or another hosted service** – one more external dependency; GitHub Actions is already where the code is.
- **Version tags for actions (`@v4`)** – simpler to read, but a moved tag changes what runs without a commit in this repository.

## Consequences

- Good: the rules in `workflow.md` and ADR 0009 are checked by a machine on every change, and a reader of the repository can see the checks pass.
- Good: the commit check and the `tdd-guard` hook share one definition of a test path (`scripts/lib/test-paths.sh`), so the agent and CI apply the same rule.
- Bad: documentation changes can fail CI on formatting. The linters run locally too, and the rules are kept minimal (`.markdownlint-cli2.jsonc`).
