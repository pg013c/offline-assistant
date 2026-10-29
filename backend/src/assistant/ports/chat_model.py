from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from assistant.domain.documents import Chunk


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

    def stream_answer(self, question: str, passages: Sequence[Chunk]) -> AsyncIterator[str]:
        """The answer as a stream of text pieces."""
        ...
