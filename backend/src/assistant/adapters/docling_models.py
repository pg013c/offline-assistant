"""The parsing models Docling loads, pinned by commit and file hash (ADR 0004, ADR 0016).

`make models` fetches these files and checks them; the API checks them again at startup, so
two machines with the same `uv.lock` parse a file into the same chunks (F-02 AC-4).
"""

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

# Weights and their configuration; READMEs and images in the repositories are not needed.
MODEL_FILE_PATTERNS = ("*.json", "*.safetensors")


class ParserNotReady(Exception):
    """A model or tool the parser needs is missing; the message says how to install it."""


@dataclass(frozen=True)
class PinnedModels:
    # Hugging Face repository -> commit.
    revisions: Mapping[str, str]
    # Path under the models directory -> SHA-256.
    files: Mapping[str, str]


PINNED_MODELS = PinnedModels(
    revisions={
        # docling-layout-heron, the default layout model of Docling 2.144 (Apache-2.0).
        "docling-project/docling-layout-heron": "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
        # TableFormer v2.3.0 (CDLA-Permissive-2.0).
        "docling-project/docling-models": "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
    },
    files={
        "docling-project--docling-layout-heron/config.json": (
            "fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d"
        ),
        "docling-project--docling-layout-heron/model.safetensors": (
            "00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c"
        ),
        "docling-project--docling-layout-heron/preprocessor_config.json": (
            "cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1"
        ),
        "docling-project--docling-models/config.json": (
            "9c34024dc28ff47b75818f415e769809798c29bf9bde6f2ccc63a4acb62396d9"
        ),
        "docling-project--docling-models/model_artifacts/tableformer/accurate/"
        "tableformer_accurate.safetensors": (
            "2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9"
        ),
        "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json": (
            "984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd"
        ),
        "docling-project--docling-models/model_artifacts/tableformer/fast/"
        "tableformer_fast.safetensors": (
            "3119563aab5a7c96fda4d621119b63fd8806272b86c30936d15507616422f718"
        ),
        "docling-project--docling-models/model_artifacts/tableformer/fast/tm_config.json": (
            "dca6762508dddfae6d57d6cb4ef822c6000119dff0f3b6489db7413118c2622a"
        ),
    },
)


def local_directory(repository: str) -> str:
    """Where Docling looks for a repository under its artifacts path."""
    return repository.replace("/", "--")


def verify_models(directory: Path, expected: Mapping[str, str]) -> None:
    """Raise `ParserNotReady` unless every expected file exists with its hash."""
    missing = sorted(path for path in expected if not (directory / path).is_file())
    different = sorted(
        path
        for path, digest in expected.items()
        if path not in missing and _sha256(directory / path) != digest
    )
    problems = [
        *(f"{path} is missing" for path in missing),
        *(f"{path} differs from the pinned version" for path in different),
    ]
    if problems:
        raise ParserNotReady(
            f"Document parsing models in {directory} are not ready: {'; '.join(problems)}. "
            "Run `make models` (the only step that needs the network)."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
