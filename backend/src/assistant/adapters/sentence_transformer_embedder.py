"""BGE-M3 through sentence-transformers, from the pinned models directory (ADR 0017)."""

from collections.abc import Sequence
from pathlib import Path


class SentenceTransformerEmbedder:
    def __init__(self, models_dir: Path) -> None:
        raise NotImplementedError

    @staticmethod
    def ensure_ready(models_dir: Path) -> None:
        raise NotImplementedError

    @property
    def model_id(self) -> str:
        raise NotImplementedError

    @property
    def dimensions(self) -> int:
        raise NotImplementedError

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError
