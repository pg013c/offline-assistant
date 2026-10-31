# 0024. Pin four candidate models for the comparison, and upgrade llama.cpp to serve them

- Status: accepted
- Date: 2026-10-31
- Related: FR-40, FR-44, FR-45, NFR-03, AI-40, AI-61, F-09b, ADR 0004, ADR 0021, ADR 0022, ADR 0023

## Context

F-09b compares five local models with the F-09a suite and its calibrated judge. The models were chosen after a check of Hugging Face on 2026-10-31: Qwen3 8B (the baseline, ADR 0021) and the four below.

- **Pinning (AI-40):** every model is pinned by revision and file hash and is fetched with its hash checked, as in ADR 0021.
- **Same conditions:** a fair comparison needs one server build, one context size and one set of prompts for every model.
- **Server support:**
  - the build installed now, llama.cpp 9960 (July 2026), predates the architectures of all four candidates: hybrid attention in Qwen3.5 and later, Gemma 4, and the ternary `Q2_0` packing (from b11556);
  - Homebrew's current llama.cpp is 0.8.0, commit `8642541`, released on 2026-10-28, 404 commits after b11556.
- **Memory:** the largest candidate (20.4 GB) runs beside the judge (18.6 GB) and the API's models within 64 GB.

## Decision

1. **Candidates:** each pinned in `pinned_models.py` and fetched by `make llm-models`. All are Apache-2.0, served locally with no network and no telemetry.

   | Model | Repository @ revision | File, size | SHA-256 |
   |---|---|---|---|
   | Qwen3.5 9B | `unsloth/Qwen3.5-9B-GGUF` @ `3885219b6810b007914f3a7950a8d1b469d598a5` | `Qwen3.5-9B-Q4_K_M.gguf`, 5.7 GB | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` |
   | Qwen3.6 35B-A3B | `ggml-org/Qwen3.6-35B-A3B-GGUF` @ `7878dc9a905c7c9379e5e8d6a1aa9affdd6839c5` | `Qwen3.6-35B-A3B-Q4_K_M.gguf`, 20.4 GB | `671e47e0ec53c665d048b98c3ecbfd5236b5ca9c3e02ed19fc8f81f7b85140c7` |
   | Gemma 4 26B-A4B | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` @ `d1c082be9cf3c8a514acf63b8761f4b41935842e` | `gemma-4-26B_q4_0-it.gguf`, 14.4 GB | `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d` |
   | Ternary-Bonsai-2 27B | `prism-ml/Ternary-Bonsai-2-27B-gguf` @ `94dd51cdbbec5309ed8b76a12f3268bc4fdceb93` | `Ternary-Bonsai-2-27B-Q2_0.gguf`, 7.6 GB | `4f99aed01b8a877e153f9aa6569a4440fe17c59701cc0953e36d7f460549e70e` |

   - **Sources:** an official build is used where one exists: llama.cpp's own `ggml-org` for Qwen3.6, and Google's quantisation-aware 4-bit build for Gemma 4. Qwen publishes no GGUF of Qwen3.5 9B, so its file comes from Unsloth.
   - **Quantisation:** each model runs in the 4-bit build its source publishes. Bonsai runs in its ternary `Q2_0` packing, the only one stock llama.cpp serves. The record names each model's quantisation.
   - **Vision:** vision towers are not fetched; the comparison is text only.
2. **Server:** llama.cpp from Homebrew, upgraded from build 9960 to 0.8.0.
   - Every report records the build, as ADR 0021 says.
   - Qwen3 8B is measured again on the new build, and the judge runs on it too. Its calibration is checked on every run anyway (ADR 0022).
3. **Serving:** `make llm` serves any registered model, chosen by name, with the same flags for each:
   - context 16k, all layers on the GPU, `--jinja`;
   - thinking off wherever the model has thinking (ADR 0021).
4. **Registry:** each candidate gets a name in `ASSISTANT_CHAT_MODEL` with its capability flags, so a switch needs no code change (FR-40).
5. **Lifetime:** the candidates stay pinned until the ADR after the runs picks the default. That ADR removes the models it does not keep.

## Alternatives considered

- **Keep build 9960 and compare older models (Qwen3 14B, gpt-oss-20b, Gemma 3):** no upgrade risk, but every candidate would be a generation behind what the project would ship.
- **The PrismML llama.cpp fork for Bonsai's denser packings (`PQ2_0`, `PTQ1_0`):**
  - smaller and faster files;
  - but a second server build, built from source, that the other models do not run on, and no Homebrew pin to record;
  - left to the backlog row on comparing servers.
- **One quantiser for every model (e.g. all Unsloth Q4_K_M):**
  - uniform format;
  - but it passes over the official builds, among them Google's quantisation-aware one, which is meant to keep quality at 4 bits;
  - Bonsai has no 4-bit build in any case.
- **Pin a llama.cpp build from GitHub releases instead of Homebrew:** an exact build, but a second install path that ADR 0021 chose not to have. The build is recorded instead.

## Consequences

- **Good:**
  - the comparison covers current models: two mixtures of experts, another family than Qwen, a ternary model and the direct successor of the default;
  - all of them are pinned, Apache-2.0 and offline.
- **Bad:**
  - about 48 GB to fetch;
  - the upgrade can change Qwen3 8B's numbers, so the earlier baseline no longer compares directly. The re-run on the new build becomes the comparison point.
  - three of the five candidates share the judge's family (ADR 0022 §4). Gemma 4 is the check within this feature, and F-09c is the check after it.
- **Follow-up:**
  - the spec's candidate table takes these files and sizes;
  - the README licence table lists the candidates;
  - `make llm-models` fetches them;
  - the ADR after the runs fixes the default and revises NFR-03.
