# F-xx. Plan

- Status: draft | approved
- Spec: [spec.md](spec.md)

## Research

What exists today that this feature touches: modules, ports, endpoints, tests. What can be reused. Risks found in the code.

## Design

Short: new or changed ports, adapters, services, endpoints, UI parts, data. A diagram only if it saves words. Decisions needing an ADR are listed here and written before step 1.

## Steps

Each step is one red commit and one green commit. Steps are ordered so that every green commit leaves `main`-quality code.

### Step 1. Short title

- Kind: code | eval | ui | infra | setup (setup: one build/ci commit, no red/green)
- Tests first: which tests or evaluation cases, in which files, asserting what
- Change: files to add or modify
- Done when: the tests pass and `make check` is green
- [ ] red
- [ ] green

### Step 2. Next title

## Acceptance criteria mapping

| AC | Proved by step |
|---|---|
| AC-1 | 1, 3 |
