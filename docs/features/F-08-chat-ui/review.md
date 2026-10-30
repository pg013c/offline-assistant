# F-08. Review

- Reviewed range: `main...feat/F-08-chat-ui` at `57592f1`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: not applicable (no model-behaviour change)
- Checks:
  - `make check` and `make e2e` pass locally, but only because `frontend/src/features/models/` exists on disk and is ignored by git (finding 1);
  - red commits precede green ones, and no green commit edits a test.
- Verification: all 12 findings confirmed; none dropped. Finding 1 was confirmed with `git ls-tree` and `git status --ignored`.

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | blocker | `.gitignore:29`, `frontend/src/features/models/` | The root pattern `models/` also ignores `frontend/src/features/models/`. `ModelSelect.tsx`, `useModels.ts` and their test were never committed, so a clean checkout cannot build `ChatView`. | AC-5, ADR 0009 | |
| 2 | minor | `Turn.tsx:50`, `useChatThread.ts:17` | The model a turn asked for is stored but not shown. A turn that fails or is stopped names no model. | AC-1 | |
| 3 | minor | `LibraryPanel.tsx:45,56` | Only the active tab panel exists, so the inactive tab's `aria-controls` names a missing element. | FE-24 | |
| 4 | minor | `LibraryPanel.tsx:57` | Switching tabs unmounts `DocumentPanel`, so an upload's progress and error are lost. | – | |
| 5 | minor | `NotesPanel.tsx:51` | `NoteView` types its props inline. | FE-22 | |
| 6 | minor | `api/schemas.py:46`, `services/models.py:46` | `ChatRequest.model` has no length limit, and the 422 message repeats it in full. | GEN-20 | |
| 7 | minor | `services/models.py:30-31` | Empty entries raise a bare `IndexError`, and duplicate ids collapse silently. | GEN-20, GEN-21 | |
| 8 | minor | `tests/conftest.py:29`, `tests/unit/api/test_health.py:8` | `ClientFor` widened to `Callable[..., TestClient]` and declared twice. Calls are no longer type-checked. | – | |
| 9 | note | `api/routes/health.py:12` | The settings dependency lives in the route module, not in `api/dependencies.py` with the others. | – | |
| 10 | note | `app.py:148-154` | The local model is offered when its server answered at startup; a server that stops later is still listed. | AC-4, decision 1 | |
| 11 | note | `spec.md` | Criteria unticked, and the criterion-to-step mapping is in the plan. TEST-09 records it in the spec. | TEST-09 | |
| 12 | note | `ChatView.tsx:48`, `Turn.tsx:47` | Ask is disabled while an answer streams, so the UI never stops a turn; `stopped` is reached only from the hook. | – | |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
