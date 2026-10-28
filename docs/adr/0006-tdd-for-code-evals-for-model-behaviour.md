# 0006. TDD for code, evaluations for model behaviour

- Status: accepted
- Date: 2026-10-28
- Related: FR-42, FR-43, ADR 0002, ADR 0009, [testing.md](../standards/testing.md)

## Context

The system has two kinds of behaviour:

- **Deterministic code**: parsing, chunking, fusion of search results, citation resolution, schema validation and retries, API routes. Unit tests describe it exactly.
- **Model behaviour**: whether the LLM picks the right tool, cites the right article, refuses an out-of-scope question. It is probabilistic, changes with the model, the prompt and the retrieval, and a single unit test says little about it.

Treating both the same way fails in one of two directions: either model behaviour is "tested" with mocks that prove nothing, or deterministic code is left to fuzzy evaluations.

## Decision

- **Deterministic code is built test first.** A failing test is written and committed before the code that makes it pass (ADR 0009). Model-backed ports are replaced by fakes in these tests.
- **Model behaviour is built evaluation first.** A change to prompts, tool schemas, retrieval parameters or the model starts by adding or updating evaluation cases in `evals/`. The change is accepted when the evaluation run meets the targets in the PRD and does not regress more than 5 points on any metric.
- **The UI is tested by behaviour**, not by markup: component tests for logic and state, and a small number of Playwright journeys. Visual layout is not test-driven.
- **Spikes are exempt.** Exploratory work (e.g. choosing a vision model) happens on a `spike/` branch without tests; the code is not merged, the conclusion becomes an ADR.

## Alternatives considered

- **TDD everywhere** – unit tests of LLM output are either flaky or tautological (they assert what the mock returns).
- **Evaluations only** – slow feedback for code that has exact, cheap tests.
- **Tests after implementation** – loses the design pressure of test first, and the commit history no longer shows the discipline.

## Consequences

- Good: each kind of behaviour has the check that actually catches its failures.
- Good: "how do you test an LLM application?" has a concrete answer in this repository.
- Bad: evaluation runs take minutes and need the model server. They run locally via `make eval` and on demand in CI, not on every push.
