"""Reranker for tests: the share of the query's words found in the passage."""

from collections.abc import Sequence

from assistant.domain.keywords import tokens


class WordOverlapReranker:
    @property
    def model_id(self) -> str:
        return "word-overlap"

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        wanted = set(tokens(query))
        if not wanted:
            return [0.0 for _ in passages]
        return [len(wanted & set(tokens(passage))) / len(wanted) for passage in passages]
