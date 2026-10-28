"""Documents as files under the data directory: `documents/<id>.txt` and `<id>.json`."""

from pathlib import Path

from assistant.domain.documents import Document


class LocalFileDocumentStore:
    def __init__(self, data_dir: Path) -> None:
        raise NotImplementedError

    def save(self, document: Document, content: str) -> None:
        raise NotImplementedError

    def list_documents(self) -> list[Document]:
        raise NotImplementedError

    def load_all(self) -> list[tuple[Document, str]]:
        raise NotImplementedError
