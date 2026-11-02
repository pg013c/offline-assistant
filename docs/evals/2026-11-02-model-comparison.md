# Five local models compared, 2026-11-02

F-09b runs five local models through the same answer suite on the same machine, graded by the same calibrated judge (FR-45). Each run passes its calibration gate. The choice of default, by the spec's selection rule, is left to the ADR of step 11.

## Setup

As in the [judged-answers record](2026-10-30-answers-judged.md), with these changes:

- **Code:** commit `ccd28f5` for every run.
- **Server:** llama.cpp 0.8.0, build `b11960-8642541b2`, from Homebrew (ADR 0024).
  - Every model is served by `make llm LLM_MODEL=<name>` on port 8080, with the same flags: context 16k, all layers on the GPU, `--jinja` and thinking off (`--reasoning off`).
  - llama-server's defaults are kept, among them a host prompt cache of up to 8 GiB (`--cache-ram 8192`).
- **Dataset:** `answers.yaml` version 5 (SHA-256 `6f316cde…`), with 47 cases, 41 of them to answer. The corpus and the retrieval settings are unchanged: reranker on, threshold 0.5.
- **Judge (ADR 0025):**
  - Gemma 4 26B-A4B QAT Q4_0, served by `make judge` on port 8081 with thinking off;
  - temperature 0, a JSON schema, up to 8192 tokens per verdict;
  - prompt SHA-256 `4268660f…dce0c0`.
- **Calibration:** `calibration.yaml` version 2, with 48 items and 74 cited sentences. The bar is 85 %.
- **Hardware:** Apple M5 Pro, 64 GB, macOS 26.4. Qdrant 1.20.0 runs in Docker.

| Model | File | Quantisation | Size | SHA-256 | Report |
|---|---|---|---|---|---|
| Qwen3 8B | `Qwen/Qwen3-8B-GGUF` | Q4_K_M | 5.0 GB | `d98cdcbd…` | `answers-qwen3-8b-20261102T140645Z.json` |
| Qwen3.5 9B | `unsloth/Qwen3.5-9B-GGUF` | Q4_K_M | 5.7 GB | `03b74727…` | `answers-qwen3.5-9b-20261102T141748Z.json` |
| Qwen3.6 35B-A3B | `ggml-org/Qwen3.6-35B-A3B-GGUF` | Q4_K_M | 20.4 GB | `671e47e0…` | `answers-qwen3.6-35b-a3b-20261102T143111Z.json` |
| Gemma 4 26B-A4B | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | QAT Q4_0 | 14.4 GB | `3eca3b8f…` | `answers-gemma-4-26b-a4b-20261102T171259Z.json` |
| Ternary-Bonsai-2 27B | `prism-ml/Ternary-Bonsai-2-27B-gguf` | Q2_0 (ternary) | 7.6 GB | `4f99aed0…` | `answers-ternary-bonsai-2-27b-20261102T165541Z.json` |

The revisions and full hashes are in ADR 0024 and in each report's metadata.

**Gemma 4's run** is judged by Gemma 4 itself and also by the check judge, Qwen3.6 35B-A3B with thinking off (ADR 0025, decision 4).
- **Ports:** a first attempt with the candidate, the judge and the check judge as three servers ran out of GPU memory while indexing. The run in the table therefore uses the candidate's own server on port 8080 as the judge: the same file, flags and name as `make judge`. The check judge ran on port 8083.
- **Memory measure:** judging starts after the answers, so the memory measure covers answering only.
- **An earlier run of Gemma 4** (`…T144203Z`, with `make judge` on port 8081) gave the same quality metrics. Its first-token median was 0.74 s and its peak memory 25 956 MiB.

## Results

| Metric | Qwen3 8B | Qwen3.5 9B | Qwen3.6 35B-A3B | Gemma 4 26B-A4B | Bonsai 27B | Cases | Floor or limit |
|---|---|---|---|---|---|---|---|
| `judged_correct` (partial counts half) | 63.4 % | 81.7 % | **84.1 %** | 79.3 % | 79.3 % | 41 | |
| correct / partial / wrong | 12 / 28 / 1 | 27 / 13 / 1 | 29 / 11 / 1 | 27 / 11 / 3 | 25 / 15 / 1 | 41 | |
| `citation_support` | 94.7 % | 97.7 % | 98.2 % | 98.2 % | 97.5 % | 57–130 sentences | 90 % |
| `tool_call_validity` | 100 % | 100 % | 100 % | 100 % | 100 % | 7–17 tool turns | 95 % |
| `out_of_scope_refused` | 100 % | 100 % | 100 % | 100 % | 100 % | 3 | 90 % |
| `not_covered_correct` | 100 % | 66.7 % | 33.3 % | 66.7 % | 66.7 % | 3 | |
| `cites_expected` | 90.2 % | 95.1 % | 95.1 % | 92.7 % | 97.6 % | 41 | |
| `answer_failed` | 0 % | 0 % | 0 % | 4.9 % | 0 % | 41 | |
| `valid_first_try` | 97.6 % | 63.4 % | 95.1 % | 92.7 % | 97.6 % | 41 | |
| `expected_tools_used` | 100 % | 71.4 % | 100 % | 83.3 % | 85.7 % | 6–7 | |
| `notes_saved_when_asked` | 66.7 % | 33.3 % | 66.7 % | 33.3 % | 66.7 % | 3 | |
| `notes_saved_unasked`, `injection_followed` | 0 % | 0 % | 0 % | 0 % | 0 % | 44, 6 | |
| First token, median | 1.14 s | 1.14 s | 0.73 s | 0.79 s | 2.85 s | | 3 s |
| First token, 95th percentile | 9.1 s | 11.7 s | 14.3 s | 9.0 s | 23.2 s | | |
| Tokens per second, median | 49 | 44 | 72 | 82 | 29 | | |
| Peak memory | 17 097 MiB | 15 785 MiB | 29 439 MiB | 26 496 MiB | 21 454 MiB | | 24 GiB (24 576 MiB) |
| Calibration, correctness / support | 97.9 / 95.9 % | 97.9 / 95.9 % | 97.9 / 95.9 % | 97.9 / 95.9 % | 97.9 / 95.9 % | 48 / 74 | 85 % |

**Peak memory** is the server's largest physical footprint while it answers, plus the size of the model file it maps (step 8). It is measured in MiB (1024 × 1024 bytes), and the spec's 24 GB limit is read as 24 GiB. Each model is on the same side of the limit under either reading. Earlier versions of this record and ADR 0026 gave these figures as GB by dividing by 1000 (review #8). Up to 8 GiB of it can be llama-server's default prompt cache, which is counted for every model as served.

**The judge's calibration** disagrees with the hand verdicts on the same 4 items in every run:
- cal-01 is labelled partial, and the judge rules it correct;
- cal-02 S1, cal-04 S1 and cal-12 S1 are labelled unsupported, and the judge rules them supported.

**The gate:**
- Qwen3 8B's run fails its gate against its own baseline of 2026-10-30, which was judged by Qwen3 30B-A3B:
  - notes saved when asked and their expected citations drop from 3 of 3 to 2 of 3;
  - citation support drops from 100 % to 94.7 %.
- The other four runs are held to the floors and calibration only, and pass.

## Gemma 4 judged twice

| Judge of Gemma 4's answers | `judged_correct` | `citation_support` | Calibration, correctness / support |
|---|---|---|---|
| Gemma 4 26B-A4B (itself) | 79.3 % | 98.2 % | 97.9 / 95.9 % |
| Qwen3.6 35B-A3B (check) | 81.7 % | 96.4 % | 95.8 / 87.8 % |

- **The two judges differ by 2.4 points** of judged correctness, within the 5 points ADR 0025 allows.
- **Gemma 4 is the stricter judge of its own answers:** on two cases (`en-ai-prohibited-practices` and `cmp-fines-ai-and-gdpr`) it rules partial where Qwen3.6 rules correct.
- **No sign of self-preference** shows in this run.

## The selection rule

The spec's rule picks, among models that meet the floors, have a median first token of 3 s or less and peak memory of 24 GiB or less, the one with the highest judged correctness. Within 5 points of each other, the faster one wins.

1. **Floors:** all five models meet them.
2. **Median first token:** all five are within 3 s. Bonsai is the closest to the limit, at 2.85 s.
3. **Peak memory:** Qwen3.6 35B-A3B (28.7 GiB) and Gemma 4 26B-A4B (25.9 GiB) exceed 24 GiB. Qwen3 8B, Qwen3.5 9B and Bonsai remain.
4. **Judged correctness:** Qwen3.5 9B scores 81.7 %. Bonsai scores 79.3 %, within 5 points, but it is slower: 2.85 s to the first token against 1.14 s, and 29 tokens per second against 44. Qwen3 8B scores 63.4 %.

**By the rule, Qwen3.5 9B is the default.** Memory was kept as measured, prompt cache included, as the human decided.

## Findings

1. **Qwen3.5 9B answers best of the models that fit,** 18 points above Qwen3 8B, in less memory. It has three weaknesses:
   - its structured answer is valid on the first try in only 63 % of cases, a mean of 1.4 attempts. Retries succeed, and no answer fails;
   - it uses the expected tools in 5 of 7 agent cases;
   - it saves 1 of 3 requested notes.

   These belong to the agent path and the answer schema, not to correctness.
2. **Qwen3.6 35B-A3B answers best overall:** 84.1 % judged correct, the fastest first token at 0.73 s, and 72 tokens per second. It misses only the memory limit, by about 4.7 GiB. Up to 8 GiB of its figure can be the prompt cache. Without that cache it might fit, and then it would win under the 5-point rule. Not measured here; that trade-off belongs to the ADR.
3. **Gemma 4 26B-A4B is the fastest generator** at 82 tokens per second. Two of its answers fail the answer schema after retries (`ref-annex-iii` and `note-checklist-en`), the same two in both of its runs.
4. **Bonsai 27B** in 7.6 GB comes within 2.4 points of Qwen3.5 9B. It is the slowest model, however: 2.85 s median first token and 23 s at the 95th percentile.
5. **No model is good at saying the documents do not cover a question.** Apart from Qwen3 8B, each misses 1 or 2 of the 3 not-covered cases, and Qwen3.6 misses 2. The sample is small.
6. **Every model refuses out-of-scope questions, follows no planted instruction and saves no unasked note.** Tool calls are valid after retries in every run.
7. **Qwen3 8B scores 63.4 % here, against 68.3 % from the old judge on 2026-10-30.** It has fewer correct answers and more partial ones: 12 / 28 / 1 here against 17 / 22 / 2. Both the server build and the judge changed between the two, so the gap cannot be split between them.

## Timing

- **Answer runs:** 9 to 15 minutes each, including indexing and judging with calibration. The judge needs about 2 minutes for the calibration set.
- **Second judging:** with the check judge on as well, Gemma 4's run took 14 minutes.
