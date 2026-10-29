"""Chunks in Qdrant: dense and BM25 vectors, fused by reciprocal rank (ADR 0017)."""

from collections.abc import Sequence

from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk
from assistant.ports.embedder import Embedder


class IndexNotReady(Exception):
    """Qdrant cannot be reached; the message says how to start it."""


def point_id(chunk_id: str) -> str:
    raise NotImplementedError


class QdrantChunkIndex:
    @classmethod
    def connect(cls, url: str, embedder: Embedder, prefix: str) -> "QdrantChunkIndex":
        raise NotImplementedError

    @property
    def collection(self) -> str:
        raise NotImplementedError

    def add(self, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        raise NotImplementedError

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def document_ids(self) -> set[str]:
        raise NotImplementedError

    def drop(self) -> None:
        """Delete the collection; for tests."""
        raise NotImplementedError
