"""Keyword terms for the BM25 half of hybrid search (ADR 0017)."""

BM25_K1 = 1.2


def tokens(text: str) -> list[str]:
    """Lower-cased words and numbers, in any script, in order."""
    raise NotImplementedError


def token_id(token: str) -> int:
    """A stable 31-bit id for a token."""
    raise NotImplementedError


def bm25_terms(text: str) -> dict[int, float]:
    """Sparse vector of the text: token id -> saturated term frequency."""
    raise NotImplementedError
