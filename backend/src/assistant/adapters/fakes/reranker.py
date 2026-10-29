"""Reranker for tests: the share of the query's words found in the passage."""

from collections.abc import Sequence


class WordOverlapReranker:
    @property
    def model_id(self) -> str:
        return "word-overlap"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        raise NotImplementedError
