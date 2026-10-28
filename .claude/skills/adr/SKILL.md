---
name: adr
description: Record an architecture decision as a numbered ADR in docs/adr/. Use when a decision is hard to reverse, adds a dependency, model, service or protocol, or changes a standard.
argument-hint: <decision in a few words>
---

# /adr <decision>

Write `docs/adr/NNNN-<kebab-title>.md` from [the template](../../../docs/adr/template.md).

## Steps

1. Read `docs/adr/README.md` for the next number and existing decisions. If an existing ADR covers the topic, the new one supersedes it: say so in both files (status line of the old one only).
2. Gather the context from the conversation, the PRD and the code. Separate facts (context) from the choice (decision).
3. List at least two real alternatives with the reason each was not chosen. If there is no real alternative, this probably does not need an ADR; say so and stop.
4. Write consequences, including the follow-up: rules to add to `docs/standards/`, backlog items, configuration.
5. For a new dependency or model, state its licence and whether it works offline.
6. Add the record to the index in `docs/adr/README.md`.
7. Show it to the human with `Status: proposed`. On acceptance set `accepted`, apply any standards change it requires in the same commit, and commit:
   `docs(adr): <title>` with `Co-Authored-By`.

## Rules

- English. One decision per record. Under one page.
- Accepted records are never rewritten; a change of mind is a new record.
