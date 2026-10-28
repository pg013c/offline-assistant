"""In-memory keyword search: the F-01 stand-in for embeddings and Qdrant (F-03)."""

from collections.abc import Sequence

from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk


class KeywordChunkIndex:
    def add(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        raise NotImplementedError
