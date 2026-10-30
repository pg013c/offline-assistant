"""Chat model fakes: a deterministic stand-in wired for tests and journeys, and a script."""

from collections.abc import AsyncIterator, Sequence

from assistant.domain.answers import (
    Answered,
    ModelAnswer,
    ModelEvent,
    ModelFailed,
    TextDelta,
    Usage,
    opening_sentences,
)
from assistant.domain.documents import Chunk
from assistant.domain.tools import FinalText, Message, ToolCalls, ToolSpec, parse_tool_calls


class FakeExtractiveChatModel:
    """Answers with the opening sentences of the best passage, and marks it cited."""

    model_id = "fake-extractive"
    is_test_model = True

    async def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        if not passages:
            return
        words = [*opening_sentences(passages[0].text).split(), "[1]"]
        for position, word in enumerate(words):
            yield TextDelta(word if position == len(words) - 1 else f"{word} ")
        yield Answered(
            ModelAnswer(text=" ".join(words), cited=(1,), covered=True),
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


class ScriptedToolCallingModel:
    """Replays tool-call replies, validating them like a real model's (F-07)."""

    def __init__(self, replies: Sequence[tuple[str, str] | str], max_retries: int = 2) -> None:
        self._replies = list(replies)
        self._max_retries = max_retries

    async def call_tools(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ToolCalls | FinalText | ModelFailed:
        by_name = {tool.name: tool for tool in tools}
        errors: list[tuple[str, str]] = []
        for attempt in range(1, self._max_retries + 2):
            reply = self._replies.pop(0)
            if isinstance(reply, str):
                return FinalText(reply)
            name, arguments = reply
            calls, errors = parse_tool_calls([(f"call-{attempt}", name, arguments)], by_name)
            if not errors:
                return ToolCalls(tuple(calls))
        return ModelFailed("invalid_answer", f"no valid tool call: {errors[0][1]}")
