"""Fetch the document parsing models into a local directory (ADR 0004, ADR 0016).

This is the only step that needs the network. Each model comes from a pinned commit, and
every file is checked against its pinned SHA-256; the API checks them again at startup. The
directory can be copied to a machine without network instead of running this script there.

Usage: python scripts/download_models.py <models-dir>
"""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

from assistant.adapters.docling_models import (
    MODEL_FILE_PATTERNS,
    PINNED_MODELS,
    local_directory,
    verify_models,
)


def main(models_dir: str) -> None:
    directory = Path(models_dir).resolve() / "docling"
    for repository, revision in PINNED_MODELS.revisions.items():
        snapshot_download(
            repo_id=repository,
            revision=revision,
            local_dir=directory / local_directory(repository),
            allow_patterns=list(MODEL_FILE_PATTERNS),
        )
    verify_models(directory, PINNED_MODELS.files)
    print(f"{len(PINNED_MODELS.files)} model files verified in {directory}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case [models_dir]:
            main(models_dir)
        case _:
            sys.exit(__doc__)
