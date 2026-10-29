"""Fetch the evaluation corpus and check it against its pinned hashes (ADR 0018).

This is the only evaluation step that needs the network. Files already present with the
right hash are not downloaded again.

Usage: python -m harness.corpus <corpus-dir>
"""

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

CORPUS_FILE = Path(__file__).parents[1] / "corpus.json"
SOURCE = "https://publications.europa.eu/resource/celex/{celex}"
TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class CorpusDocument:
    file: str
    title: str
    celex: str
    language: str
    accept: str
    sha256: str


def documents() -> list[CorpusDocument]:
    """The documents of the corpus, as pinned in corpus.json."""
    entries = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))["documents"]
    return [CorpusDocument(**entry) for entry in entries]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for document in documents():
        target = directory / document.file
        if target.exists() and sha256(target) == document.sha256:
            print(f"present    {document.file}")
            continue
        response = httpx.get(
            SOURCE.format(celex=document.celex),
            headers={"Accept": document.accept, "Accept-Language": document.language},
            follow_redirects=True,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        actual = hashlib.sha256(response.content).hexdigest()
        if actual != document.sha256:
            sys.exit(f"{document.file}: SHA-256 {actual} differs from the pinned {document.sha256}")
        target.write_bytes(response.content)
        print(f"downloaded {document.file}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case [directory]:
            fetch(Path(directory))
        case _:
            sys.exit(__doc__)
