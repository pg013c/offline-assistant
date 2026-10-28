"""Documents as files under the data directory: `documents/<id>.txt` and `<id>.json`."""

import json
from dataclasses import asdict
from pathlib import Path

from assistant.domain.documents import Document


class LocalFileDocumentStore:
    def __init__(self, data_dir: Path) -> None:
        self._directory = data_dir / "documents"

    def save(self, document: Document, content: str) -> None:
        metadata = self._directory / f"{document.id}.json"
        if metadata.exists():
            return
        self._directory.mkdir(parents=True, exist_ok=True)
        (self._directory / f"{document.id}.txt").write_text(content, encoding="utf-8")
        # Metadata last: a document counts as stored only once both files exist.
        metadata.write_text(json.dumps(asdict(document)), encoding="utf-8")

    def list_documents(self) -> list[Document]:
        return [document for document, _ in self.load_all()]

    def load_all(self) -> list[tuple[Document, str]]:
        if not self._directory.exists():
            return []
        stored = []
        for metadata in sorted(self._directory.glob("*.json")):
            document = Document(**json.loads(metadata.read_text(encoding="utf-8")))
            content = metadata.with_suffix(".txt").read_text(encoding="utf-8")
            stored.append((document, content))
        return stored
