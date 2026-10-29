# F-04. Review

- Reviewed range: `main...feat/F-04-evaluation-harness` at `12556ea`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: first run sets the baseline, [2026-10-29-retrieval-baseline.md](../../evals/2026-10-29-retrieval-baseline.md) (recall@3 52.4 %, recall@10 76.2 %, MRR 0.422; 21 in-scope and 3 out-of-scope cases). A second run gave identical numbers and passed the gate.
- Checks: `make check` (with `make check-evals`), `make test-integration`, `make e2e` and `make eval` pass. Red commits precede green ones.
- Verification: all 14 findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `evals/harness/run.py:144-166`, `main()` | `data/eval` and the `eval` collection persist between runs, and an upload of known bytes returns the stored document, so later runs score the old index. After a chunking or indexing change, `make eval` would measure the old code and pass the gate. | AC-2, AC-6, AI-31, AI-61 | fix |
| 2 | minor | `evals/harness/report.py:20-33` | The report does not record the resolved expected chunk ids, although the spec says it does. | spec decision 3, AC-6 | fix |
| 3 | minor | `evals/harness/run.py:147-166` | Corpus files are uploaded without checking their hashes; a missing file is skipped and fails later as "matches no chunk"; with no file present the run waits 30 minutes; the failure check looks at every stored document; corpus hashes are not in the metadata. | ADR 0018, AI-61 | fix |
| 4 | minor | `evals/harness/run.py:130-141` | The health wait accepts any API already listening on the evaluation port, so the corpus could go into another server's data. | AC-2 | fix |
| 5 | minor | `evals/harness/metrics.py:84-93`, `gate.py:17-20` | In-scope cases below the threshold are not listed as missed, and the gate silently skips a baseline metric missing from the current run. | AC-5, AC-7 | fix |
| 6 | minor | `evals/tests/` | No tests for downloading only missing corpus files (AC-1), for `make eval` exiting on a regression (AC-7), or for the missing-baseline message. | TEST-09, AC-1, AC-7 | fix |
| 7 | minor | `scripts/lib/test-paths.sh:9` | The test-path rule was narrowed after the green commits that relied on it, in a commit that also changed its test; `evals/promptfoo/*` and `evals/corpus.json` are now unprotected evaluation inputs. | ADR 0009, TEST-22 | fix |
| 8 | minor | `evals/datasets/retrieval.yaml:69-88` | Cross-language cases count the same article in the question's language as a miss, because the corpus holds both languages; the baseline is partly an artefact of this. | TEST-21, spec | fix |
| 9 | minor | `evals/harness/run.py:109`, `:198-217`, `promptfoo.py:28` | No timeout on the Promptfoo run, an API log file that is never closed, and a bare `KeyError` when a case has no output. | AI-22 | fix |
| 10 | note | `evals/harness/gate.py:35` | One in-scope case is 4.76 points, so a single-case regression never trips the 5-point gate; MRR is gated as if it were a share. | AC-7, PRD §9 | fix |
| 11 | note | `run.py:296-299`, `Makefile:10-12` | The evaluated threshold and Qdrant URL can come from a developer's `.env`; the Qdrant preflight checks `QDRANT_PORT` while the run uses `ASSISTANT_QDRANT_URL`. | AI-61 | fix |
| 12 | note | `run.py:200-216`, `docs/architecture.md:174` | Promptfoo also stores each run in its database under the home directory (no `--no-write`), and it is missing from the telemetry list. | ADR 0018 | fix |
| 13 | note | `retrieval.yaml:103-112`, spec | Spans-articles cases count a hit on either article, and the `heading` source form is not in the spec; neither is recorded as deliberate. | spec | fix |
| 14 | note | `docs/evals/2026-10-29-retrieval-baseline.md:12` | The indexing time against NFR-05 is stated but not measured by the harness. | plan step 8, NFR-05 | fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
