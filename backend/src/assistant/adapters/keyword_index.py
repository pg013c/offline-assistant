"""In-memory keyword search: the F-01 stand-in for embeddings and Qdrant (F-03)."""

import re
from collections.abc import Sequence

from assistant.domain.documents import Chunk
from assistant.ports.chunk_index import ScoredChunk

_WORD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "its",
        "may",
        "must",
        "not",
        "of",
        "on",
        "or",
        "shall",
        "should",
        "that",
        "the",
        "their",
        "there",
        "these",
        "this",
        "those",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
    ]
)


def keywords(text: str) -> frozenset[str]:
    """Lower-cased words of the text without stop words."""
    return frozenset(_WORD.findall(text.lower())) - _STOP_WORDS


class KeywordChunkIndex:
    """Scores a chunk by how many distinct query keywords it contains."""

    def __init__(self) -> None:
        self._entries: list[tuple[Chunk, frozenset[str]]] = []

    def add(self, chunks: Sequence[Chunk]) -> None:
        self._entries.extend((chunk, keywords(chunk.text)) for chunk in chunks)

    def search(self, query: str, limit: int) -> list[ScoredChunk]:
        wanted = keywords(query)
        scored = [
            ScoredChunk(chunk=chunk, score=float(len(wanted & words)))
            for chunk, words in self._entries
        ]
        matches = [result for result in scored if result.score > 0]
        return sorted(matches, key=lambda result: result.score, reverse=True)[:limit]

    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    def document_ids(self) -> set[str]:
        raise NotImplementedError
