from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from assistant.domain.answers import ModelEvent, ModelFailed
from assistant.domain.documents import Chunk
from assistant.domain.tools import FinalText, Message, ToolCalls, ToolSpec


class ChatModel(Protocol):
    """A language model that answers a question from the given passages."""

    @property
    def model_id(self) -> str:
        """Name and version of the model, shown with every answer."""
        ...

    @property
    def is_test_model(self) -> bool:
        """True for stand-ins that are not language models; the UI must say so (AC-8)."""
        ...

    def answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[ModelEvent]:
        """Text deltas of each attempt, ending with exactly one `Answered` or `ModelFailed`.

        An attempt whose output was rejected is followed by `AttemptDiscarded`; the text of the
        last attempt is the answer. Passages are numbered from 1 in the order given.
        """
        ...


class ToolCallingModel(Protocol):
    """A chat model that can call tools; the agent drives it turn by turn (F-07)."""

    async def call_tools(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> ToolCalls | FinalText | ModelFailed:
        """The model's next turn: tool calls with validated arguments, or its final text.

        Unknown tools and invalid arguments are retried with the error fed back (AI-21);
        after the last retry the turn is `ModelFailed`.
        """
        ...
