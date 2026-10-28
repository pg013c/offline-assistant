"""Deterministic stand-in for a language model, wired in production until F-06."""

from collections.abc import AsyncIterator, Sequence

from assistant.domain.documents import Chunk


class FakeExtractiveChatModel:
    model_id = "fake-extractive"

    async def stream_answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""
