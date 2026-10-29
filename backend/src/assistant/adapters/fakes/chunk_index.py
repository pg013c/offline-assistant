"""ChunkIndex for tests: the fake embedder and BM25 terms in memory, fused like Qdrant."""

from collections.abc import Sequence

from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk
from assistant.ports.embedder import Embedder


class InMemoryChunkIndex:
    def __init__(self, embedder: Embedder | None = None) -> None:
        raise NotImplementedError

    def add(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def document_ids(self) -> set[str]:
        raise NotImplementedError
