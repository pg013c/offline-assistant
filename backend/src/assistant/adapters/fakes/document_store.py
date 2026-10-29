"""In-memory DocumentStore for tests."""

from assistant.domain.documents import Document


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
