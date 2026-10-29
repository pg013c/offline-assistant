# 0021. Serve the local LLM with llama.cpp's llama-server, starting with Qwen3 8B

- Status: accepted
- Date: 2026-10-29
- Related: FR-13, FR-15, FR-40, FR-44, NFR-03, AI-23, AI-40 to AI-42, AI-50, AI-51, F-06, ADR 0003, ADR 0004, ADR 0007, ADR 0016

## Context

F-06 replaces the test model with a real local LLM.

- **Interface:** ADR 0003 fixes the OpenAI-compatible Chat Completions API.
- **Where it runs:** ADR 0007 runs the LLM server natively on the Mac. It names Ollama as the default and `mlx_lm.server` as the alternative, and leaves the choice to measurements.
- **Model:** FR-40 fixes the exact model versions in an ADR after the first evaluation run (F-09). Until then development needs one default model.

The server and the model must:

- **Offline (ADR 0004):** run with no network at runtime and no telemetry.
- **Exact pinning (AI-40):** a file hash, not a moving tag, as for the parsing, embedding and reranking models (ADR 0016).
- **Features:** serve streamed responses, JSON-schema constrained output and tool calls, which F-06 and F-07 need.
- **Fit:** run on the reference Mac (Apple M5 Pro, 64 GB) alongside the API's models, within NFR-03's 3 s to the first token.

On the reference Mac, llama.cpp's `llama-server` is already installed through Homebrew (build 9960). Ollama and MLX are not installed.

## Decision

1. **Server:** llama.cpp's `llama-server` (MIT), installed with Homebrew and run natively with Metal.
   - `make llm` starts it on 127.0.0.1 with the pinned model file. It uses:
     - the model's own chat template (`--jinja`), for tool calls;
     - all layers on the GPU;
     - a context of 16k tokens;
     - Qwen3's thinking turned off, because answers need speed, not visible reasoning.
   - `llama-server` sends nothing over the network and has no telemetry.
   - The build in use is recorded in every evaluation report.
2. **Default model until F-09:** Qwen3 8B, the official `Qwen/Qwen3-8B-GGUF` repository, file `Qwen3-8B-Q4_K_M.gguf`.
   - Licence Apache-2.0, 5.0 GB.
   - Pinned to revision `7c41481f57cb95916b40956ab2f0b139b296d974` and SHA-256 `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785`.
   - It is multilingual including Polish and is trained for tool calling.
3. **Fetching:** `make llm-models` fetches the LLM files and checks their hashes.
   - They are kept apart from `make models`, so CI and developers who use only the test model do not download 5 GB.
   - The API does not load the LLM. At startup it checks that the configured server answers and serves the configured model, and fails with the command to run if not.
4. **Client:** the adapter talks to the server with httpx (BSD-3-Clause), declared as a runtime dependency of the backend. It is already installed through qdrant-client and imported by the Qdrant adapter; until now it was declared only for tests. No OpenAI SDK: the API surface we use is small, and one client less keeps the adapter's behaviour explicit.
5. **Configuration (AI-23):** each model in `ASSISTANT_CHAT_MODEL` has a base URL, a served model name, a pinned file and its capability flags. `fake-extractive` stays for tests and the browser journeys.

## Alternatives considered

- **Ollama** (ADR 0007's default):
  - convenient, but not installed;
  - it pins models by registry tag rather than by file hash;
  - it unloads idle models after five minutes, which adds cold starts to measurements;
  - it runs llama.cpp underneath anyway.
- **`mlx_lm.server`:**
  - possibly faster on Apple Silicon;
  - but it needs its own Python environment;
  - its tool calling and JSON-schema support are less mature than llama.cpp's.

  F-09 measures it against llama.cpp with the same adapter.
- **The OpenAI Python SDK** – a well-known client, but a new dependency with its own retries and timeouts layered over ours (AI-21, AI-22), for a few endpoints httpx covers.
- **LM Studio** – a GUI application under a proprietary licence. It is not scriptable for `make` and CI-like runs.
- **A larger default (Qwen3 14B or 30B-A3B)** – better answers likely, but slower and heavier while the pipeline is being built. F-09 compares them.

## Consequences

- **Good:**
  - every model in the project is pinned by file hash;
  - one native install that is already present;
  - the same adapter serves every server F-09 compares.
- **Bad:**
  - Homebrew updates llama.cpp independently, so the build is recorded, not pinned;
  - 5 GB more to fetch for real answers;
  - one more process to start (`make llm`).
- **Follow-up:**
  - ADR 0007 is amended: llama.cpp is the default on macOS, and Ollama and MLX remain candidates for F-09;
  - the model goes in the README licence table;
  - `make llm` and `make llm-models` are added;
  - F-09's ADR fixes the final model versions (FR-40).
