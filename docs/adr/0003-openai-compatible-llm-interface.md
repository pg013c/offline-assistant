# 0003. OpenAI-compatible API as the only LLM interface

- Status: accepted
- Date: 2026-10-28
- Related: FR-40, FR-41, FR-51, ADR 0002

## Context

We want to compare local models served by Ollama, MLX (`mlx_lm.server`), llama.cpp (`llama-server`) and vLLM, plus Claude as a cloud reference. All local servers expose an OpenAI-compatible Chat Completions API, including tool calling and, with varying quality, JSON schema constrained output.

## Decision

The `ChatModel` port has one production adapter for local models, `OpenAICompatibleChat`, configured by base URL, model name and capability flags (supports tools, supports JSON schema, supports streaming). Switching between Ollama, MLX, llama.cpp and vLLM is configuration only.

Claude gets its own adapter (`AnthropicChat`) behind the same port, used only in comparison mode (ADR 0004).

Server-specific features (e.g. llama.cpp GBNF grammars, vLLM guided decoding) are used only through options of the OpenAI-compatible API, never through a second client.

## Alternatives considered

- **Native client per server** – more features, but N adapters to maintain and a comparison that measures the clients, not the models.
- **LiteLLM as an abstraction** – adds a dependency and its own failure modes for something that one small adapter covers.

## Consequences

- Good: one code path for every local model; the evaluation compares models, not integrations.
- Bad: we only get features the compatible API exposes. Differences in tool-calling support between servers are recorded in capability flags and in the evaluation report.
