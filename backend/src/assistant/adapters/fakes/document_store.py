"""In-memory DocumentStore for tests."""

from collections.abc import Sequence

from assistant.domain.documents import Chunk, Document


class FakeDocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, tuple[Document, str]] = {}

    def save(self, document: Document, content: str) -> None:
        self._documents.setdefault(document.id, (document, content))

    def list_documents(self) -> list[Document]:
        return [document for document, _ in self._documents.values()]

    def load_all(self) -> list[tuple[Document, str]]:
        return list(self._documents.values())

    def get(self, document_id: str) -> Document | None:
        stored = self._documents.get(document_id)
        return stored[0] if stored else None

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
