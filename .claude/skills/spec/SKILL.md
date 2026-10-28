---
name: spec
description: Write the specification of one backlog feature (docs/features/F-xx-*/spec.md) through a short interview with the human. Use at the start of every feature, before any plan or code.
argument-hint: F-xx
---

# /spec F-xx

Produce `docs/features/F-xx-<short-name>/spec.md` from [the template](../../../docs/features/_templates/spec.md). The spec states intent and acceptance criteria. It contains no design and no implementation steps; those belong to `/plan-feature`.

## Steps

1. Read the feature's row in `docs/backlog.md`, the referenced requirement ids in `docs/prd.md`, the related ADRs, and any spec of a feature it depends on. If the id is not in the backlog, stop and ask.
2. Create the branch `feat/F-xx-<short-name>` from an up-to-date `main` if it does not exist.
3. Draft the spec. Then ask the human only what you cannot answer from the documents or the code, in one batch of at most five questions, each with your recommended answer. Typical gaps: edge cases, what "done" looks like for the demo, what is explicitly out of scope.
4. Write acceptance criteria that are observable and testable (Given/When/Then). Each one must later map to a test or an evaluation case.
5. If the feature changes model behaviour (prompts, tools, retrieval, model choice), add evaluation cases to the spec's table: input, expected sources, expected behaviour. Include at least one out-of-scope or adversarial case. See `docs/standards/testing.md` TEST-20/21.
6. List any decision that needs an ADR under open questions, with a suggestion to run `/adr`.
7. Set the backlog status to `spec`.
8. Show the spec to the human and wait for approval. On approval set `Status: approved` and commit:
   `docs(F-xx): add spec` with trailers `Refs: F-xx` and `Co-Authored-By`.

## Rules

- Write in English.
- Keep it to one page. If it grows beyond that, propose splitting the feature in the backlog.
- Do not start planning or coding in this skill.
