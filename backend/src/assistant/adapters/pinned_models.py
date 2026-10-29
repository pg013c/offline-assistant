"""Every model the app loads, pinned by commit and file hash (ADR 0004, ADR 0016, ADR 0017)."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from assistant.adapters.docling_models import ParserNotReady

__all__ = ["BGE_M3", "PINNED_MODELS", "ParserNotReady", "PinnedModel", "verify_models"]


@dataclass(frozen=True)
class PinnedModel:
    repository: str
    revision: str
    # Where the files live, relative to ASSISTANT_MODELS_DIR.
    directory: str
    # Path under `directory` -> SHA-256.
    files: Mapping[str, str]


BGE_M3 = PinnedModel(repository="BAAI/bge-m3", revision="", directory="", files={})
PINNED_MODELS: tuple[PinnedModel, ...] = ()


def verify_models(models_dir: Path, models: Iterable[PinnedModel]) -> None:
    """Raise `ParserNotReady` unless every file of every model exists with its hash."""
    raise NotImplementedError
