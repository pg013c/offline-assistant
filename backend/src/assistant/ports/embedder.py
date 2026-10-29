from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Turns text into dense vectors of unit length, comparable by dot product."""

    @property
    def model_id(self) -> str:
        """Name and pinned version of the model; an index is built for one model."""
        ...

    @property
    def dimensions(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Vectors of passages, in order."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Vector of a search query."""
        ...
