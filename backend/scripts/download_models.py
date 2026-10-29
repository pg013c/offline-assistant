"""Fetch the document parsing models into a local directory (ADR 0004, ADR 0015).

This is the only step that needs the network. It writes `manifest.json` with the SHA-256 of
every file, which the API checks at startup; the directory can be copied to a machine
without network instead of running this script there.

Usage: python scripts/download_models.py <models-dir>
"""

import hashlib
import json
import sys
from pathlib import Path

from docling.utils.model_downloader import download_models

MANIFEST = "manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory: Path) -> int:
    # Hugging Face download bookkeeping under `.cache` changes between runs; it is not a model.
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.name != MANIFEST and ".cache" not in path.parts
    )
    manifest = {str(path.relative_to(directory)): sha256(path) for path in files}
    (directory / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return len(manifest)


def main(models_dir: str) -> None:
    directory = Path(models_dir).resolve() / "docling"
    # Layout and table structure only; OCR is Tesseract, everything else stays off (ADR 0015).
    download_models(
        output_dir=directory,
        progress=True,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=False,
    )
    count = write_manifest(directory)
    print(f"{count} model files in {directory}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case [models_dir]:
            main(models_dir)
        case _:
            sys.exit(__doc__)
