"""ChunkIndex for tests: dense vectors and BM25 terms in memory, fused like the Qdrant index.

Unlike Qdrant's dense search, it returns only chunks that share something with the query,
so tests of "no relevant passage" do not depend on a similarity threshold.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from assistant.adapters.fakes.embedder import FakeEmbedder
from assistant.domain.documents import Chunk
from assistant.domain.keywords import bm25_terms, tokens
from assistant.ports.chunk_index import ScoredChunk
from assistant.ports.embedder import Embedder

# Reciprocal rank fusion constant, as in Qdrant.
RRF_K = 60


@dataclass(frozen=True)
class _Entry:
    chunk: Chunk
    vector: list[float]
    terms: dict[int, float]


class InMemoryChunkIndex:
    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder or FakeEmbedder()
        self._entries: dict[str, _Entry] = {}

    def add(self, chunks: Sequence[Chunk]) -> None:
        vectors = self._embedder.embed([chunk.text for chunk in chunks])
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._entries[chunk.id] = _Entry(chunk, vector, bm25_terms(chunk.text))

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        if not tokens(query) or not self._entries:
            return []
        query_vector = self._embedder.embed_query(query)
        similarity = {
            key: sum(a * b for a, b in zip(query_vector, entry.vector, strict=True))
            for key, entry in self._entries.items()
        }
        keyword = self._bm25(bm25_terms(query))
        fused: dict[str, float] = {}
        for ranking in (similarity, keyword):
            ordered = sorted((key for key in ranking if ranking[key] > 0), key=ranking.__getitem__)
            for rank, key in enumerate(reversed(ordered)):
                fused[key] = fused.get(key, 0.0) + 1 / (RRF_K + rank + 1)
        # Ties go to the closer meaning, as in the Qdrant index.
        best = sorted(fused, key=lambda key: (-fused[key], -similarity[key], key))[:limit]
        return [
            ScoredChunk(
                chunk=self._entries[key].chunk,
                score=fused[key],
                similarity=max(similarity[key], 0.0),
            )
            for key in best
        ]

    def remove_document(self, document_id: str) -> None:
        self._entries = {
            key: entry
            for key, entry in self._entries.items()
            if entry.chunk.document_id != document_id
        }

    def document_ids(self) -> set[str]:
        return {entry.chunk.document_id for entry in self._entries.values()}

    def _bm25(self, query_terms: dict[int, float]) -> dict[str, float]:
        """Term weights times inverse document frequency, as Qdrant's IDF modifier does."""
        count = len(self._entries)
        scores: dict[str, float] = {}
        for term in query_terms:
            holders = [key for key, entry in self._entries.items() if term in entry.terms]
            idf = math.log(1 + (count - len(holders) + 0.5) / (len(holders) + 0.5))
            for key in holders:
                scores[key] = scores.get(key, 0.0) + self._entries[key].terms[term] * idf
        return scores
