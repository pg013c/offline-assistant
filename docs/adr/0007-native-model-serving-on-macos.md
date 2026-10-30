# 0007. Native model serving on macOS

- Status: accepted, amended by [0021](0021-llama-server-and-qwen3-8b.md)
- Date: 2026-10-28
- Related: FR-51, NFR-03, ADR 0003

## Context

The reference machine is a MacBook Pro with Apple M5 Pro and 64 GB unified memory. Containers on macOS run in a Linux VM with no access to the Apple GPU (Metal), so an LLM inside Docker runs on CPU and is several times slower. vLLM targets NVIDIA GPUs and does not use Metal.

## Decision

- On macOS, the LLM server runs natively on the host. Supported: Ollama (default for convenience) and `mlx_lm.server` (expected to be faster on Apple Silicon). The choice between them is made from measurements in milestone 3 and recorded in a new ADR.
- Containers reach it at `host.docker.internal`.
- Embeddings, reranker and speech models run in the API process. In development the API runs natively (`make dev`) to use Metal through PyTorch MPS where it helps; in Docker it runs on CPU, which is acceptable for these smaller models and is measured.
- On Linux with an NVIDIA GPU, the `gpu` Compose profile runs vLLM in a container.

## Alternatives considered

- **Everything in Docker on macOS** – simplest to describe, but CPU-only inference would make the latency targets impossible and the demo misleading.
- **Everything native, no Docker** – fastest, but loses the reproducible, offline-installable package that FR-52 asks for.

## Consequences

- Good: real performance on the reference hardware, and an honest comparison between Apple Silicon and a GPU server.
- Bad: the macOS setup has one native component to install (Ollama or MLX), documented in the README and the offline guide.
