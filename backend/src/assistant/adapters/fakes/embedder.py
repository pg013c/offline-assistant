"""Embedder for tests: hashed bag of words, with a few Polish words mapped to English."""

from collections.abc import Sequence


class FakeEmbedder:
    @property
    def model_id(self) -> str:
        return "fake-embedder"

    @property
    def dimensions(self) -> int:
        return 256

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError
