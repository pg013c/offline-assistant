"""BGE reranker v2 M3 through sentence-transformers, from the pinned models directory (ADR 0019).

The model loads on first use: it takes seconds and about 2.3 GB of memory.
"""

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from assistant.adapters.model_loading import MODEL_LOADING
from assistant.adapters.pinned_models import BGE_RERANKER, verify_models

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

BATCH_SIZE = 16


def precision_for(device: str) -> str:
    """The floating-point precision the model runs in on a device.

    Float16 halves the scoring time on Apple GPUs and keeps scores within 0.01 (F-05);
    CPUs gain little from it, so they keep float32.
    """
    return "float16" if device == "mps" else "float32"


class BgeReranker:
    def __init__(self, models_dir: Path, device: str | None = None) -> None:
        self._path = models_dir / BGE_RERANKER.directory
        self._device = device
        self._model: CrossEncoder | None = None
        self._lock = threading.Lock()

    @staticmethod
    def default_device() -> str:
        """The device the model runs on unless told otherwise: the Apple GPU if there is one."""
        import torch

        return "mps" if torch.backends.mps.is_available() else "cpu"

    @staticmethod
    def ensure_ready(models_dir: Path) -> None:
        """Raise `ModelsNotReady` unless the pinned reranker files are in place."""
        verify_models(models_dir, [BGE_RERANKER])

    @property
    def model_id(self) -> str:
        return f"{BGE_RERANKER.repository}@{BGE_RERANKER.revision[:8]}"

    @property
    def precision(self) -> str:
        """The precision of the loaded model, as a torch dtype name."""
        model = self._get_model().model
        if model is None:
            raise RuntimeError("the reranker has no model loaded")
        return str(model.dtype).removeprefix("torch.")

    def score(self, query: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        # One output per pair, passed through a sigmoid: 0 to 1, higher is more relevant.
        scores = self._get_model().predict(
            [(query, passage) for passage in passages],
            batch_size=BATCH_SIZE,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [float(score) for score in scores]

    def _get_model(self) -> "CrossEncoder":
        with self._lock:
            if self._model is None:
                self._model = self._load()
            return self._model

    def _load(self) -> "CrossEncoder":
        with MODEL_LOADING:
            import torch
            from sentence_transformers import CrossEncoder

            device = self._device or self.default_device()
            model: CrossEncoder = CrossEncoder(
                str(self._path),
                device=device,
                local_files_only=True,
                model_kwargs={"torch_dtype": getattr(torch, precision_for(device))},
            )
            return model
