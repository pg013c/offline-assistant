"""Deterministic stand-in for a language model, wired in production until F-06."""

from collections.abc import AsyncIterator, Sequence

from assistant.domain.answers import ModelEvent, opening_sentences
from assistant.domain.documents import Chunk


class FakeExtractiveChatModel:
    """Answers with the opening sentences of the best passage, the same text it cites."""

    model_id = "fake-extractive"
    is_test_model = True

    async def stream_answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[str]:
        if not passages:
            return
        words = opening_sentences(passages[0].text).split()
        for position, word in enumerate(words):
            yield word if position == len(words) - 1 else f"{word} "

    def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        raise NotImplementedError


class ScriptedChatModel:
    """Replays a fixed list of events, whatever it is asked; counts its calls."""

    is_test_model = False

    def __init__(self, events: Sequence[ModelEvent], model_id: str = "scripted") -> None:
        self.model_id = model_id
        self._events = list(events)
        self.calls = 0

    async def stream_answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[str]:
        raise NotImplementedError
        yield ""

    def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        raise NotImplementedError
