"""Documents as files under the data directory.

`documents/<id><ext>` is the upload as received, `<id>.json` its metadata and
`<id>.chunks.json` its chunks once parsed.
"""

import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path, PurePath
from typing import Any

from assistant.domain.documents import Chunk, ChunkLocation, Document

_METADATA = ".json"
_CHUNKS = ".chunks.json"


class LocalFileDocumentStore:
    def __init__(self, data_dir: Path) -> None:
        self._directory = data_dir / "documents"

    def save_upload(self, document: Document, content: bytes) -> None:
        if self._path(document.id, _METADATA).exists():
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        self._original_path(document).write_bytes(content)
        # Metadata last: a document counts as stored only once its original exists.
        self.update(document)

    def update(self, document: Document) -> None:
        self._write_json(self._path(document.id, _METADATA), asdict(document))

    def load_original(self, document_id: str) -> bytes:
        document = self.get(document_id)
        if document is None:
            raise KeyError(document_id)
        return self._original_path(document).read_bytes()

    def save_chunks(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        self._write_json(self._path(document_id, _CHUNKS), [asdict(chunk) for chunk in chunks])

    def load_chunks(self, document_id: str) -> list[Chunk]:
        path = self._path(document_id, _CHUNKS)
        if not path.exists():
            return []
        return [_chunk_from(record) for record in json.loads(path.read_text(encoding="utf-8"))]

    def get(self, document_id: str) -> Document | None:
        metadata = self._path(document_id, _METADATA)
        return _read_metadata(metadata) if metadata.exists() else None

    def list_documents(self) -> list[Document]:
        if not self._directory.exists():
            return []
        files = sorted(self._directory.glob(f"*{_METADATA}"))
        return [_read_metadata(path) for path in files if not path.name.endswith(_CHUNKS)]

    def delete(self, document_id: str) -> None:
        raise NotImplementedError

    def _path(self, document_id: str, suffix: str) -> Path:
        return self._directory / f"{document_id}{suffix}"

    def _original_path(self, document: Document) -> Path:
        return self._path(document.id, PurePath(document.filename).suffix.lower())

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        # Write then rename, so a reader never sees half a file.
        # A name per writer, so two threads saving the same document do not share a file.
        partial = path.with_name(f"{path.name}.{uuid.uuid4().hex}.partial")
        partial.write_text(json.dumps(value), encoding="utf-8")
        partial.replace(path)


def _read_metadata(path: Path) -> Document:
    record = json.loads(path.read_text(encoding="utf-8"))
    # F-01 stored no status and no chunks; such documents are parsed again.
    record.setdefault("status", "processing")
    return Document(**record)


def _chunk_from(record: dict[str, Any]) -> Chunk:
    location = record.pop("location")
    location["heading_path"] = tuple(location["heading_path"])
    return Chunk(**record, location=ChunkLocation(**location))
