"""Fetch the models the app loads into a local directory (ADR 0004, ADR 0016, ADR 0017).

This is the only step that needs the network. Each model comes from a pinned commit, only
the files the app loads are fetched, and every file is checked against its pinned SHA-256;
the API checks them again at startup. The directory can be copied to a machine without
network instead of running this script there.

Usage: python scripts/download_models.py <models-dir>
"""

import sys
from pathlib import Path

from huggingface_hub import snapshot_download

from assistant.adapters.pinned_models import PINNED_MODELS, verify_models


def main(models_dir: str) -> None:
    directory = Path(models_dir).resolve()
    for model in PINNED_MODELS:
        snapshot_download(
            repo_id=model.repository,
            revision=model.revision,
            local_dir=directory / model.directory,
            allow_patterns=list(model.files),
        )
    verify_models(directory, PINNED_MODELS)
    files = sum(len(model.files) for model in PINNED_MODELS)
    print(f"{len(PINNED_MODELS)} models, {files} files verified in {directory}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case [models_dir]:
            main(models_dir)
        case _:
            sys.exit(__doc__)
