# 0022. Judge answers with a local Qwen3 30B-A3B, and floor citation support and tool-call validity

- Status: accepted
- Date: 2026-10-30
- Related: FR-42, FR-43, PRD §9, AI-12, AI-31, AI-40, AI-61, TEST-24, F-09a, ADR 0004, ADR 0006, ADR 0018, ADR 0020, ADR 0021

## Context

PRD §9 sets targets that need judgement, not string checks:

- **Citation accuracy ≥ 90 %:** the cited passage supports the claim;
- **Answer correctness:** judged, and reported per model.

PRD §9 also sets valid tool calls ≥ 95 %. The answer suite today scores only whether a citation hits an expected chunk.

**Requirements for the judge:**

- read an answer, its question, a reference answer of key points, and the cited passages;
- return verdicts as validated structured output;
- run in the evaluation only, never in the API;
- run offline like everything else (ADR 0004);
- be pinned by file hash (AI-40, ADR 0021).

**Constraints on the reference Mac** (Apple M5 Pro, 64 GB): the judge must fit beside Qwen3 8B (5 GB) and the API's models, and judge about 45 answers in minutes, not hours.

The judged model is Qwen3 8B now; F-09b compares other local models with the same judge.

## Decision

1. **Judge model:** Qwen3 30B-A3B, the official `Qwen/Qwen3-30B-A3B-GGUF` repository, file `Qwen3-30B-A3B-Q4_K_M.gguf`.
   - Licence Apache-2.0, 18.6 GB.
   - Pinned to revision `e4d4bafdfb96a411a163846265362aceb0b9c63a` and SHA-256 `0d003f6662faee786ed5da3e31b29c978de5ae5d275c8794c606a7f3c01aa8f5`.
   - A mixture of experts with about 3B active parameters, so it is about as fast as an 8B model while knowing more.
2. **Serving:** llama.cpp's `llama-server`, as in ADR 0021.
   - `make judge` serves it on its own port (`JUDGE_PORT`, default 8081), thinking off.
   - `make judge-models` fetches it and checks its hash, apart from `make llm-models`.
   - The evaluation harness calls it through the OpenAI-compatible API with a JSON schema. The API never does.
3. **Calibration:**
   - the judge is checked against verdicts written by hand on a sample of answers, recorded in the repository;
   - each judged run reports its agreement with them;
   - below 85 % agreement for correctness or for support, the run fails rather than report numbers nobody can trust.
4. **Same-family bias:** the judge and the default model are both Qwen3. The record names this, and F-09c has Claude re-judge a sample to measure it.
5. **Answer gate (amends TEST-24 for the answer suite):**
   - **citation support:** floor 90 %;
   - **tool-call validity after retries:** floor 95 %;
   - both as PRD §9 sets them;
   - **judged correctness:** held to the 5-point regression rule only, until F-09b sets a target.

## Alternatives considered

- **Claude as the judge now:**
  - stronger, and outside the Qwen family;
  - but it needs network mode, an API key and money on every run, and it waits for F-09c's adapter;
  - kept as the cross-check.
- **Qwen3 32B dense:**
  - possibly a little more accurate;
  - but about four times slower per token on the reference Mac, which turns a run into an hour.
- **A different family, e.g. Gemma 3 27B or gpt-oss-20b:**
  - avoids the same-family bias;
  - but both are F-09b candidates, so the judge would grade itself there instead;
  - Qwen3 30B-A3B is not a candidate for the default model, being too large to keep beside the API's models.
- **No model, overlap with the reference text:**
  - free and deterministic;
  - but it misses paraphrase and Polish inflection;
  - it cannot tell whether a passage supports a sentence.

## Consequences

- **Good:**
  - PRD §9's citation and tool targets become gated measures;
  - correctness gets a number per model;
  - every model in the project stays pinned and offline.
- **Bad:**
  - 18.6 GB more to fetch, and one more process for a judged run;
  - verdicts from a model are noisy, which is why calibration gates them;
  - the same-family bias remains until F-09c measures it.
- **Follow-up:**
  - TEST-24 lists the answer floors;
  - the judge goes in the README licence table and `pinned_models.py`;
  - `make judge` and `make judge-models` are added;
  - F-09b keeps this judge for the comparison;
  - F-09c re-judges a sample with Claude.
