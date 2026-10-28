---
name: plan-feature
description: Research the codebase and write the step-by-step implementation plan for an approved feature spec (docs/features/F-xx-*/plan.md). Each step names its tests first. Use after /spec is approved, before /tdd.
argument-hint: F-xx
---

# /plan-feature F-xx

Produce `plan.md` next to the approved `spec.md`, from [the template](../../../docs/features/_templates/plan.md).

## Steps

1. Read `spec.md`. If its status is not `approved`, stop and say so.
2. Research before designing. Read the code the feature touches: ports, services, adapters, routes, UI features, existing tests and fakes. Use a read-only subagent (Explore) if more than a handful of files are involved, and keep only its conclusions. Write the findings in the Research section: what exists, what to reuse, what is risky.
3. Design briefly: new or changed ports, adapters, services, endpoints, UI parts, evaluation cases. Check it against `docs/architecture.md` and the ADRs. A decision that needs an ADR is written with `/adr` before step 1 of the plan.
4. Split the work into steps of a size that one red commit and one green commit can cover (typically 15–60 minutes of work). Order them so that each green commit leaves the branch in a state fit for `main`:
   - ports, fakes and contract tests before real adapters,
   - services before routes, routes before UI,
   - `make api-client` regeneration in the step that changes the API,
   - for model behaviour: evaluation cases in their own step, before the prompt or retrieval change.
5. For each step write: kind (`code`, `eval`, `ui`, `infra`), the tests or evaluation cases to write first and what they assert, the files to change, and when it is done.
6. Map every acceptance criterion to at least one step. A criterion without a step means the plan is incomplete.
7. Set backlog status to `building`. Show the plan to the human and wait for approval. On approval set `Status: approved` and commit:
   `docs(F-xx): add plan` with `Refs: F-xx` and `Co-Authored-By`.

## Rules

- English. No code in the plan beyond signatures where they clarify a port or schema.
- Apply `docs/standards/`; do not restate them in the plan.
- If the spec turns out to be wrong or incomplete, stop and propose a spec change rather than planning around it.
