from collections.abc import Sequence
from typing import Protocol


class Reranker(Protocol):
    """Scores how well each passage answers a query, reading both together (ADR 0019)."""

    @property
    def model_id(self) -> str:
        """Name and pinned version of the model."""
        ...

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        """One score per passage, in order; higher is better, comparable within one call."""
        ...
