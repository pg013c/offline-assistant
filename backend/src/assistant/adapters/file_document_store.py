"""Documents as files under the data directory: `documents/<id>.txt` and `<id>.json`."""

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from assistant.domain.documents import Chunk, Document


class LocalFileDocumentStore:
    def __init__(self, data_dir: Path) -> None:
        self._directory = data_dir / "documents"

    def save(self, document: Document, content: str) -> None:
        metadata = self._metadata_path(document.id)
        if metadata.exists():
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        (self._directory / f"{document.id}.txt").write_text(content, encoding="utf-8")
        # Metadata last: a document counts as stored only once both files exist.
        metadata.write_text(json.dumps(asdict(document)), encoding="utf-8")

    def get(self, document_id: str) -> Document | None:
        metadata = self._metadata_path(document_id)
        return self._read_metadata(metadata) if metadata.exists() else None

    def list_documents(self) -> list[Document]:
        return [self._read_metadata(metadata) for metadata in self._metadata_files()]

    def load_all(self) -> list[tuple[Document, str]]:
        return [
            (
                self._read_metadata(metadata),
                metadata.with_suffix(".txt").read_text(encoding="utf-8"),
            )
            for metadata in self._metadata_files()
        ]

    def _metadata_path(self, document_id: str) -> Path:
        return self._directory / f"{document_id}.json"

    def _metadata_files(self) -> list[Path]:
        return sorted(self._directory.glob("*.json")) if self._directory.exists() else []

    @staticmethod
    def _read_metadata(path: Path) -> Document:
        return Document(**json.loads(path.read_text(encoding="utf-8")))

    def save_upload(self, document: Document, content: bytes) -> None:
        raise NotImplementedError

    def update(self, document: Document) -> None:
        raise NotImplementedError

    def load_original(self, document_id: str) -> bytes:
        raise NotImplementedError

    def save_chunks(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        raise NotImplementedError

    def load_chunks(self, document_id: str) -> list[Chunk]:
        raise NotImplementedError
