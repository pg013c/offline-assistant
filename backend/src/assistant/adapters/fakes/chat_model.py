"""Chat model fakes: a deterministic stand-in wired for tests and journeys, and a script."""

from collections.abc import AsyncIterator, Sequence

from assistant.domain.answers import (
    Answered,
    ModelAnswer,
    ModelEvent,
    TextDelta,
    Usage,
    opening_sentences,
)
from assistant.domain.documents import Chunk


class FakeExtractiveChatModel:
    """Answers with the opening sentences of the best passage, and cites it."""

    model_id = "fake-extractive"
    is_test_model = True

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        if not passages:
            return
        text = opening_sentences(passages[0].text)
        words = text.split()
        for position, word in enumerate(words):
            yield TextDelta(word if position == len(words) - 1 else f"{word} ")
        yield Answered(
            ModelAnswer(text=" ".join(words), cited=(1,)),
            Usage(
                prompt_tokens=0, completion_tokens=0, first_token_ms=0.0, total_ms=0.0, attempts=1
            ),
        )


class ScriptedChatModel:
    """Replays a fixed list of events, whatever it is asked; counts its calls."""

    is_test_model = False

    def __init__(self, events: Sequence[ModelEvent], model_id: str = "scripted") -> None:
        self.model_id = model_id
        self._events = list(events)
        self.calls = 0

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        self.calls += 1
        for event in self._events:
            yield event
