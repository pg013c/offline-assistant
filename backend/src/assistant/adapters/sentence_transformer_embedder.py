"""BGE-M3 through sentence-transformers, from the pinned models directory (ADR 0017).

The model loads on first use: it takes seconds and about 2 GB of memory.
"""

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from assistant.adapters.pinned_models import BGE_M3, verify_models

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

DIMENSIONS = 1024
BATCH_SIZE = 16


class SentenceTransformerEmbedder:
    def __init__(self, models_dir: Path, device: str | None = None) -> None:
        self._path = models_dir / BGE_M3.directory
        self._device = device
        self._model: SentenceTransformer | None = None
        self._lock = threading.Lock()

    @staticmethod
    def ensure_ready(models_dir: Path) -> None:
        """Raise `ModelsNotReady` unless the pinned BGE-M3 files are in place."""
        verify_models(models_dir, [BGE_M3])

    @property
    def model_id(self) -> str:
        return f"{BGE_M3.repository}@{BGE_M3.revision[:8]}"

    @property
    def dimensions(self) -> int:
        return DIMENSIONS

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(
            list(texts), batch_size=BATCH_SIZE, normalize_embeddings=True, convert_to_numpy=True
        )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        # BGE-M3 needs no query instruction.
        return self.embed([text])[0]

    def _get_model(self) -> "SentenceTransformer":
        with self._lock:
            if self._model is None:
                import torch
                from sentence_transformers import SentenceTransformer

                device = self._device or ("mps" if torch.backends.mps.is_available() else "cpu")
                self._model = SentenceTransformer(
                    str(self._path), device=device, local_files_only=True
                )
            return self._model
