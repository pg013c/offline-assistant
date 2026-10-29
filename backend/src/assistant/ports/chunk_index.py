from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from assistant.domain.documents import Chunk


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk: Chunk
    # Rank score of the fused result list; only its order means anything.
    score: float
    # Dense cosine similarity to the query, comparable across queries; 0 when only the keyword
    # half found the chunk.
    similarity: float = 0.0


class ChunkIndex(Protocol):
    """Searchable store of chunks: dense and keyword search, fused (ADR 0017).

    It is derived from the stored chunks and can be rebuilt from them.
    """

    def add(self, chunks: Sequence[Chunk]) -> None:
        """Make the chunks searchable; chunks already indexed are replaced, not duplicated."""
        ...

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        """Best-matching chunks for the query, best first; empty when nothing matches."""
        ...

    def remove_document(self, document_id: str) -> None:
        """Remove every chunk of the document."""
        ...

    def document_ids(self) -> set[str]:
        """Ids of the documents that have chunks in the index."""
        ...
