from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from assistant.domain.documents import Chunk


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk: Chunk
    score: float


class ChunkIndex(Protocol):
    """Searchable store of chunks."""

    def add(self, chunks: Sequence[Chunk]) -> None:
        """Make the chunks searchable."""
        ...

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        """Best-matching chunks for the query, best first; empty when nothing matches."""
        ...
