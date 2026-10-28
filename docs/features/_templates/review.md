# F-xx. Review

- Reviewed range: `main..feat/F-xx-...` at `<commit>`
- Reviewer: `reviewer` agent, fresh context
- Evaluation: `<result summary or "not applicable">`

## Findings

Severity: **blocker** (must fix before merge), **major** (should fix in this feature), **minor** (fix or move to backlog), **note** (no action).

| # | Severity | Where | Finding | Standard | Decision |
|---|---|---|---|---|---|
| 1 | major | `backend/src/assistant/services/agent.py:42` | Retries are unbounded when the model returns invalid JSON | ai.md §3 | fix |

Decision is filled in by the human: `fix`, `backlog (F-xx)`, or `reject: <reason>`.

## Resolution

| # | Commits |
|---|---|
| 1 | `abc1234` test, `def5678` fix |
