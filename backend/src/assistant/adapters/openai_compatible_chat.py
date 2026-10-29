"""A chat model behind any OpenAI-compatible server: llama.cpp, Ollama, MLX, vLLM (ADR 0003)."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import httpx

from assistant.domain.answers import ModelEvent
from assistant.domain.documents import Chunk


@dataclass(frozen=True)
class LlmServer:
    """Where a model is served and how long and how often to try it (AI-21, AI-22)."""

    base_url: str
    served_model: str
    timeout_seconds: float
    max_retries: int


class OpenAICompatibleChat:
    is_test_model = False

    def __init__(
        self,
        *,
        model_id: str,
        server: LlmServer,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model_id = model_id

    def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        raise NotImplementedError
