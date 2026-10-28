from typing import Protocol

from assistant.domain.documents import Document


class DocumentStore(Protocol):
    """Durable storage of uploaded documents and their text."""

    def save(self, document: Document, content: str) -> None:
        """Store the document; saving an existing document again changes nothing."""
        ...

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        ...

    def load_all(self) -> list[tuple[Document, str]]:
        """All stored documents with their text, to rebuild indexes at startup."""
        ...
