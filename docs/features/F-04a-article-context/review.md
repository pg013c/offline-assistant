# F-04a. Review

- Reviewed range: `main...feat/F-04a-article-context` at `60847c8`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-29-retrieval-article-context.md](../../evals/2026-10-29-retrieval-article-context.md). Against the F-04 baseline: recall@3 61.9 → 90.5 %, recall@10 81.0 → 100 %, MRR 0.573 → 0.821, out-of-scope refusals 3/3.
- Checks: `make check`, `make test-integration`, `make e2e` and `make eval` pass. Red commits precede green ones.
- Verification: all 9 findings confirmed against the code; findings 1 and 2 reproduced. None dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `domain/documents.py:194-199`, `:238-244` | A title-like paragraph becomes a title even when no content follows it under its heading. Followed by another heading, it disappears from the index: "Main Street 5, 00-001 Warsaw" under "Address" yields no chunk. A Markdown file with one heading and one short line yields no chunks at all and would fail. | FR-03, AC-2 | |
| 2 | major | `tests/unit/services/test_document_service.py:542-553` | The test that documents of the current chunker are not parsed again cannot fail: the parser's assertion is caught by the service, and the only check holds either way. | TEST-01, AC-3 | |
| 3 | minor | `plan.md` steps 4a and 5, `spec.md` | The annex rule (chunker version 3) was added after the first measurement failed AC-4. The human approved it in the session, but the decision is not recorded in the repository, and the spec's scope and decisions do not mention annexes. | workflow | |
| 4 | minor | `test_document_service.py:518-539` | The re-parse test feeds the same blocks before and after, so it would pass even if stale stored chunks were re-indexed under the new version; "chunk ids follow the new chunking" is not tested. | AC-3 | |
| 5 | minor | `domain/documents.py:157-161` | The case of an annex label directly after an article heading (it must not become the article's title) is not tested. | TEST-09 | |
| 6 | minor | `docs/evals/2026-10-29-retrieval-baseline.md:3, :48` | The superseded F-04 record still calls itself the baseline `make eval` gates against. | – | |
| 7 | note | `docs/evals/2026-10-29-retrieval-article-context.md:32`, `docs/architecture.md` | The out-of-scope similarity figures (0.38, 0.33) are not in any result file, and architecture.md still says 0.33. | AI-61 | |
| 8 | note | `spec.md` | Acceptance criteria are not ticked and the mapping to proofs is only in the plan (done at ship time). | TEST-09 | |
| 9 | note | `docs/evals/retrieval-baseline.json` `expected` | Several expected chunk ids shifted because title chunks were removed, and the unchanged F-02 snapshot re-check is not stated anywhere. | AC-6 | |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
