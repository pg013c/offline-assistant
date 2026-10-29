"""Embedder for tests: hashed bag of words, with a few Polish words mapped to English.

Texts sharing words are close, and the small table lets tests ask in Polish about English
text, as BGE-M3 allows for real.
"""

import math
from collections.abc import Sequence

from assistant.domain.keywords import token_id, tokens

_POLISH_TO_ENGLISH = {
    "kiedy": "when",
    "jest": "is",
    "systemu": "system",
    "sztucznej": "ai",
    "inteligencji": "ai",
    "wysokiego": "high",
    "ryzyka": "risk",
    "dostawcy": "providers",
    "przechowują": "keep",
    "rejestry": "logs",
    "załącznik": "annex",
}


class FakeEmbedder:
    @property
    def model_id(self) -> str:
        return "fake-embedder"

    @property
    def dimensions(self) -> int:
        return 256

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in tokens(text):
            vector[token_id(_POLISH_TO_ENGLISH.get(word, word)) % self.dimensions] += 1.0
        length = math.hypot(*vector)
        if length == 0:
            # Text without words still gets a unit vector, unlike any word's.
            return [1.0, *[0.0] * (self.dimensions - 1)]
        return [value / length for value in vector]
