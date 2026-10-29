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
| 1 | `2dd8eef` test, `30e81f7` fix (each run empties its data directory and drops its own collections; the integration test runs twice) |
| 2 | `0dc2c06` test, `3a11bcc` fix |
| 3 | `2dd8eef` test, `30e81f7` fix (corpus verified against its pins first; hashes in the metadata; waits only for corpus documents) |
| 4 | `2dd8eef` test, `30e81f7` fix (a busy port is refused) |
| 5 | `0dc2c06` test, `3a11bcc` fix |
| 6 | `0dc2c06` test, `3a11bcc` fix (corpus download with an injected client; `make eval` exit and the missing-baseline message) |
| 7 | `100f65f` test, `502f80d` build; the commit that added the Promptfoo suite was split so the suite lands in its own `test(eval)` commit (`857deec`) |
| 8 | `f2f21a4` test(eval), dataset version 2; baseline recorded again in `01271a5` |
| 9 | `0dc2c06` test, `3a11bcc` fix (named error for a case without output); `30e81f7` (Promptfoo timeout, log closed) |
| 10 | `01271a5` docs (gate sensitivity in the baseline record) |
| 11 | `2dd8eef` test, `30e81f7` fix (fixed threshold, Qdrant from `QDRANT_PORT`, no `ASSISTANT_*` inherited) |
| 12 | `998d797` test, `6f6a1b4` fix (`--no-write`, `--no-share`); `40a5c43` docs (telemetry list) |
| 13 | `40a5c43` docs (`plan.md`, "Changes during the build") |
| 14 | `30e81f7` fix (indexing time in the metadata), `01271a5` docs (97.7 s for 464 pages) |
