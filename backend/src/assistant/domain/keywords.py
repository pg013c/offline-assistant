"""Keyword terms for the BM25 half of hybrid search (ADR 0017).

Qdrant applies the inverse document frequency; this module supplies the term side. There is
no stemming, so the same word in another grammatical form is another term; the dense half
covers that.
"""

import hashlib
import re
from collections import Counter

BM25_K1 = 1.2
_TOKEN = re.compile(r"[^\W_]+")
_ID_BITS = 31


def tokens(text: str) -> list[str]:
    """Lower-cased words and numbers, in any script, in order."""
    return _TOKEN.findall(text.lower())


def token_id(token: str) -> int:
    """A stable 31-bit id for a token, the same in every process and on every machine."""
    digest = hashlib.sha256(token.encode()).digest()
    return int.from_bytes(digest[:4], "big") & ((1 << _ID_BITS) - 1)


def bm25_terms(text: str) -> dict[int, float]:
    """Sparse vector of the text: token id -> saturated term frequency.

    Chunks are short and bounded in length, so there is no length normalisation.
    """
    weights: dict[int, float] = {}
    for token, count in Counter(tokens(text)).items():
        key = token_id(token)
        # Two tokens may share an id; their weights add up.
        weights[key] = weights.get(key, 0.0) + count * (BM25_K1 + 1) / (count + BM25_K1)
    return weights
