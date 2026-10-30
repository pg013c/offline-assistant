"""Fetch the evaluation corpus and check it against its pinned hashes (ADR 0018).

This is the only evaluation step that needs the network. Files already present with the
right hash are not downloaded again; files kept in the repository are copied (F-07).

Usage: python -m harness.corpus <corpus-dir>
"""

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

EVALS_DIR = Path(__file__).parents[1]
CORPUS_FILE = EVALS_DIR / "corpus.json"
SOURCE = "https://publications.europa.eu/resource/celex/{celex}"
TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class CorpusDocument:
    file: str
    title: str
    language: str
    sha256: str
    # Downloaded from EUR-Lex by CELEX number, or copied from `path` under evals/ (F-07).
    celex: str | None = None
    accept: str | None = None
    path: str | None = None
    # Indexed only by the answer suite, so retrieval metrics stay comparable.
    answers_only: bool = False


def documents() -> list[CorpusDocument]:
    """The documents of the corpus, as pinned in corpus.json."""
    entries = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))["documents"]
    return [CorpusDocument(**entry) for entry in entries]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(directory: Path, client: httpx.Client | None = None) -> None:
    """Download each pinned file that is missing or differs; keep only matching downloads."""
    directory.mkdir(parents=True, exist_ok=True)
    with client or httpx.Client(follow_redirects=True, timeout=TIMEOUT_SECONDS) as http:
        for document in documents():
            target = directory / document.file
            if target.exists() and sha256(target) == document.sha256:
                print(f"present    {document.file}")
                continue
            if document.path is not None:
                content = (EVALS_DIR / document.path).read_bytes()
                action = "copied    "
            else:
                response = http.get(
                    SOURCE.format(celex=document.celex),
                    headers={
                        "Accept": document.accept or "application/pdf",
                        "Accept-Language": document.language,
                    },
                )
                response.raise_for_status()
                content = response.content
                action = "downloaded"
            actual = hashlib.sha256(content).hexdigest()
            if actual != document.sha256:
                sys.exit(
                    f"{document.file}: SHA-256 {actual} differs from the pinned {document.sha256}"
                )
            target.write_bytes(content)
            print(f"{action} {document.file}")


if __name__ == "__main__":
    match sys.argv[1:]:
        case [directory]:
            fetch(Path(directory))
        case _:
            sys.exit(__doc__)
