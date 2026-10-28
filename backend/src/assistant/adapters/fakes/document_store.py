"""In-memory DocumentStore for tests."""

from assistant.domain.documents import Document


class FakeDocumentStore:
    def save(self, document: Document, content: str) -> None:
        raise NotImplementedError

    def list_documents(self) -> list[Document]:
        raise NotImplementedError

    def load_all(self) -> list[tuple[Document, str]]:
        raise NotImplementedError
