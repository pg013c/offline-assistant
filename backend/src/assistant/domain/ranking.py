"""Ordering search candidates by a reranker's scores (F-05)."""

from collections.abc import Sequence


def rerank[T](candidates: Sequence[T], scores: Sequence[float]) -> list[tuple[T, float]]:
    """Candidates with their scores, highest first; equal scores keep the candidates' order."""
    raise NotImplementedError
