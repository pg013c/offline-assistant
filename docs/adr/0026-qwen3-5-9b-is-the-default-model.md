# 0026. Qwen3.5 9B is the default model; NFR-03 and the correctness target are revised

- Status: accepted
- Date: 2026-11-02
- Related: FR-40, NFR-03, PRD §9, F-09b, ADR 0021, ADR 0022, ADR 0024, ADR 0025
- Amends: ADR 0021, decision 2 (the default model)

## Context

The [comparison record of 2026-11-02](../evals/2026-11-02-model-comparison.md) ran five pinned models through the answer suite. The setup was the same for all five:

- llama.cpp `b11960`;
- the same flags and the reference Mac;
- the Gemma 4 judge, which passed calibration in every run at 97.9 % and 95.9 %.

| Model | Judged correct | Median / p95 first token | Peak memory |
|---|---|---|---|
| Qwen3 8B | 63.4 % | 1.14 / 9.1 s | 17.1 GB |
| Qwen3.5 9B | 81.7 % | 1.14 / 11.7 s | 15.8 GB |
| Qwen3.6 35B-A3B | 84.1 % | 0.73 / 14.3 s | 29.4 GB |
| Gemma 4 26B-A4B | 79.3 % | 0.79 / 9.0 s | 26.5 GB |
| Ternary-Bonsai-2 27B | 79.3 % | 2.85 / 23.2 s | 21.5 GB |

**The spec's rule:**
- among models that meet the floors, with a median first token of at most 3 s and peak memory of at most 24 GB, the highest judged correctness wins;
- within 5 points, the faster model wins.

**What the record shows:**
- all five meet the floors;
- Qwen3.6 and Gemma 4 exceed the memory limit. Peak memory counts llama-server's default prompt cache of up to 8 GiB, and the human chose to keep that measure;
- Qwen3.5 9B beats Bonsai by 2.4 points and is faster.

**Qwen3.5 9B's weaknesses:**
- its structured answer is valid on the first try in 63 % of cases, a mean of 1.4 attempts;
- it uses the expected tools in 5 of 7 agent cases;
- it saves 1 of 3 requested notes.

**What the PRD leaves open:**
- NFR-03 (first token at most 3 s) is an initial target, to be revised once after the first measured baseline;
- PRD §9 sets no correctness target until there is a baseline.

## Decision

1. **Default model: Qwen3.5 9B**, `unsloth/Qwen3.5-9B-GGUF` @ `3885219b6810b007914f3a7950a8d1b469d598a5`, file `Qwen3.5-9B-Q4_K_M.gguf`, SHA-256 `03b74727…52b7e8` (ADR 0024).
   - It is Apache-2.0 and 5.7 GB, served by `make llm` with the flags of ADR 0024.
   - It becomes the default of `ASSISTANT_CHAT_MODEL`, `LLM_MODEL` in `make llm`, and the answer run.
2. **Pins kept:**
   - Qwen3.5 9B, the default;
   - Qwen3.6 35B-A3B and Gemma 4 26B-A4B. They stay pinned as the judge and its check (ADR 0025), and stay selectable as chat models for side-by-side use.
3. **Pins removed:**
   - Qwen3 8B, which Qwen3.5 9B beats on quality and memory;
   - Ternary-Bonsai-2 27B, the slowest model, with no role left.

   Both leave `pinned_models.py`, the registry, `make llm-models` and the README.
4. **NFR-03 revised:** for the default model on the reference Mac, measured by `make eval-answers`:
   - median time to first token at most **2 s**;
   - 95th percentile at most **15 s**, which covers the agent path with tool turns.

   Every answer record reports both. The answer gate does not enforce them yet, because timing varies with what else is loaded; the M5 performance run does.
5. **Judged-correctness target (PRD §9):** at least **75 %** for the default model, judged by a calibrated judge.
   - Below it, a change does not merge, as for the other §9 targets.
   - The 5-point regression rule from the baseline stays.
6. **Baseline:** a run of Qwen3.5 9B replaces `docs/evals/answer-baseline.json`. Every later answer run of the default is held to it.

## Alternatives considered

- **Qwen3.6 35B-A3B, with `--cache-ram` lowered to fit 24 GB:**
  - it has the best correctness (84.1 %) and the fastest first token (0.73 s);
  - but it needs a server flag change for one model and a new measurement;
  - its 20.4 GB file leaves less room for the speech models of M3 and M4;
  - the human kept the measure as it is. It stays pinned, so it can be revisited with that measurement.
- **Keep Qwen3 8B:** the code changes least. But it is 18 points below Qwen3.5 9B and uses more memory.
- **Ternary-Bonsai-2 27B:** close on correctness, but 2.85 s to the first token and 23 s at the 95th percentile, near the NFR-03 limit.
- **Correctness target at 80 %:**
  - it is closer to the measured 81.7 %;
  - but it leaves less margin than the run-to-run spread seen so far: Qwen3 8B measured 64–68 % across runs;
  - a target that fails on noise would block merges for nothing.

## Consequences

- **Good:**
  - the default answers 18 points better than before, in less memory, at the same speed;
  - NFR-03 and PRD §9 become measured targets with a margin.
- **Bad:**
  - Qwen3.5 9B retries its structured answer more often. That adds latency to the 95th percentile, and its note and tool use is weaker than Qwen3 8B's;
  - the default and the check judge share the Qwen family. The Gemma 4 judge keeps the main verdicts outside it.
  - Tests that use `qwen3-8b` as a sample name move to `qwen3.5-9b`.
- **Follow-up:**
  - **Step 11:** the defaults in `Settings`, `make llm`, `default_answers_config` and the README; the removed pins; the new baseline;
  - **PRD:** NFR-03 and §9 change in the commit of this ADR;
  - **Backlog:**
    - first-try validity of Qwen3.5 9B's structured answers;
    - its note and tool use;
    - not-covered answers across all models.
