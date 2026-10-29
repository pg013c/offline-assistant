"""BGE reranker v2 M3 through sentence-transformers, from the pinned models directory (ADR 0019)."""

from collections.abc import Sequence
from pathlib import Path


class BgeReranker:
    def __init__(self, models_dir: Path, device: str | None = None) -> None:
        self._models_dir = models_dir
        self._device = device

    @staticmethod
    def ensure_ready(models_dir: Path) -> None:
        raise NotImplementedError

    @property
    def model_id(self) -> str:
        raise NotImplementedError

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        raise NotImplementedError
