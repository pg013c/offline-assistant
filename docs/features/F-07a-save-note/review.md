# F-07a. Review

- Reviewed range: `main...feat/F-07a-save-note` at `875ca41`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: [2026-10-30-answers-notes.md](../../evals/2026-10-30-answers-notes.md), 29 answer cases.
  - notes saved when asked 2/2, unasked 0/31;
  - cites an expected passage 86.2 %;
  - language match 100 %;
  - injection followed 0/3;
  - agent path 5.6 s median.
- Checks:
  - `make check` passes;
  - the agent integration tests pass against Qwen3 8B;
  - red commits precede green ones, and no green commit edits a test.
- Verification: all 10 findings confirmed against the code; none dropped.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `services/agent.py:132`, `prompts/agent.md` | The answer call gets only the question and passages. It is never told whether a note was saved, so it can say "saved" after a failed save, and cannot name the note. | AC-1, spec Scope | |
| 2 | minor | `services/agent.py:100-121` | A `save_note` that fails in the last allowed turn is never shown to the model again. With 2 turns, gather-then-save puts the save in that turn. | AC-4, AI-21 | |
| 3 | minor | `services/tools.py:129` | Any line ending in a colon skips the marker check, and nothing requires one marker overall. A one-line note ending in ":" is saved with no sources. | AI-01, FR-11, AC-4 | |
| 4 | minor | `adapters/file_note_store.py:37-55` | Saves are not atomic (`.json`, then `.md`), and `list_notes` parses every `*.json`. One bad file makes `GET /api/notes` a 500. | AC-5 | |
| 5 | minor | `evals/datasets/answers.yaml` (`inj-save-note`) | The injection case does not ask for a note, so `save_note` is never offered. No case tests a planted instruction while the model holds `save_note`. | AI-12 | |
| 6 | minor | `evals/harness/answers.py:286-292` | Note cases score that a note was saved, not what it cites. The spec expects Art. 26 and Art. 33 (PL) in the notes. | AC-6 | |
| 7 | minor | `domain/tools.py` (`SaveNoteArguments`) | No unit test keeps `pattern` and `maxLength` out of the schema sent to the model. Only the live-model test would catch the grammar failure again. | TEST-09, AI-20 | |
| 8 | note | `adapters/file_note_store.py:1-4` | Each note is two files, `.md` and a `.json` sidecar. The spec says one Markdown file, and the plan does not record the sidecar. | AC-1 | |
| 9 | note | `services/agent.py:111-120` | Nothing limits a run to one note. Several `save_note` calls with different arguments write several files. | spec Scope | |
| 10 | note | `prompts/agent.md:12` | The language prompt change was measured together with the tool-cap change, not on its own. | AI-31 | |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
