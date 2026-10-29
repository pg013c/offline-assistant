"""The parsing models Docling loads, pinned by commit and file hash (ADR 0004, ADR 0015)."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


class ParserNotReady(Exception):
    """A model or tool the parser needs is missing; the message says how to install it."""


@dataclass(frozen=True)
class PinnedModels:
    # Hugging Face repository -> commit.
    revisions: Mapping[str, str]
    # Path under the models directory -> SHA-256.
    files: Mapping[str, str]


PINNED_MODELS = PinnedModels(revisions={}, files={})


def verify_models(directory: Path, expected: Mapping[str, str]) -> None:
    """Raise `ParserNotReady` unless every expected file exists with its hash."""
    raise NotImplementedError
