"""Ordering search candidates by a reranker's scores (F-05)."""

from collections.abc import Sequence


def rerank[T](candidates: Sequence[T], scores: Sequence[float]) -> list[tuple[T, float]]:
    """Candidates with their scores, highest first; equal scores keep the candidates' order."""
    if len(candidates) != len(scores):
        raise ValueError(f"{len(candidates)} candidates, {len(scores)} scores")
    # `sorted` is stable, so ties stay in the order the candidates came in.
    return sorted(zip(candidates, scores, strict=True), key=lambda pair: -pair[1])
