# F-08. Review

- Reviewed range: `main...feat/F-08-chat-ui` at `57592f1`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: not applicable (no model-behaviour change)
- Checks:
  - `make check` and `make e2e` pass locally, but only because `frontend/src/features/models/` exists on disk and is ignored by git (finding 1);
  - red commits precede green ones, and no green commit edits a test.
- Decisions: by the human on 2026-10-30, as recommended.
- Verification: all 12 findings confirmed; none dropped. Finding 1 was confirmed with `git ls-tree` and `git status --ignored`.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | blocker | `.gitignore:29`, `frontend/src/features/models/` | The root pattern `models/` also ignores `frontend/src/features/models/`. `ModelSelect.tsx`, `useModels.ts` and their test were never committed, so a clean checkout cannot build `ChatView`. | AC-5, ADR 0009 |  fix: anchor the rule to the root (`/models/`); the test in a red commit, the code in a green one |
| 2 | minor | `Turn.tsx:50`, `useChatThread.ts:17` | The model a turn asked for is stored but not shown. A turn that fails or is stopped names no model. | AC-1 |  fix: a turn shows the model it asked for until its answer names one |
| 3 | minor | `LibraryPanel.tsx:45,56` | Only the active tab panel exists, so the inactive tab's `aria-controls` names a missing element. | FE-24 |  fix: both tab panels stay mounted, the inactive one hidden |
| 4 | minor | `LibraryPanel.tsx:57` | Switching tabs unmounts `DocumentPanel`, so an upload's progress and error are lost. | – |  fix: as 3 |
| 5 | minor | `NotesPanel.tsx:51` | `NoteView` types its props inline. | FE-22 |  fix |
| 6 | minor | `api/schemas.py:46`, `services/models.py:46` | `ChatRequest.model` has no length limit, and the 422 message repeats it in full. | GEN-20 |  fix: at most 100 characters |
| 7 | minor | `services/models.py:30-31` | Empty entries raise a bare `IndexError`, and duplicate ids collapse silently. | GEN-20, GEN-21 |  fix: a ValueError for no entries or a repeated id |
| 8 | minor | `tests/conftest.py:29`, `tests/unit/api/test_health.py:8` | `ClientFor` widened to `Callable[..., TestClient]` and declared twice. Calls are no longer type-checked. | – |  fix: one `ClientFor` protocol |
| 9 | note | `api/routes/health.py:12` | The settings dependency lives in the route module, not in `api/dependencies.py` with the others. | – |  fix: `get_settings` in `api/dependencies.py` |
| 10 | note | `app.py:148-154` | The local model is offered when its server answered at startup; a server that stops later is still listed. | AC-4, decision 1 |  fix: the limitation is recorded in the spec; checking the server on each listing goes with F-09 |
| 11 | note | `spec.md` | Criteria unticked, and the criterion-to-step mapping is in the plan. TEST-09 records it in the spec. | TEST-09 |  fix: at /ship |
| 12 | note | `ChatView.tsx:48`, `Turn.tsx:47` | Ask is disabled while an answer streams, so the UI never stops a turn; `stopped` is reached only from the hook. | – |  fix: asking while an answer streams stops it |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `092f9d3` test, `1bd2a48` fix (`.gitignore`: `/models/` and `data/models/`) |
| 2 | `952fb39` test, `9b340e1` fix |
| 3 | `3873bc8` test, `ddb00ed` test (a hidden panel found by id), `d5de355` fix |
| 4 | as 3 |
| 5 | `d5de355` fix |
| 6 | `fadcb8b` test, `bd3d4d1` fix |
| 7 | `fadcb8b` test, `bd3d4d1` fix |
| 8 | `fadcb8b` test |
| 9 | `bd3d4d1` fix |
| 10 | docs commit (spec decision 1) |
| 11 | at /ship |
| 12 | `952fb39` test, `9b340e1` fix |
