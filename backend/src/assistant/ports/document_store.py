from collections.abc import Sequence
from typing import Protocol

from assistant.domain.documents import Chunk, Document


class DocumentStore(Protocol):
    """Durable storage of uploaded files, their metadata and their chunks."""

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        ...

    def save_upload(self, document: Document, content: bytes) -> None:
        """Store an uploaded file and its metadata; an existing document stays unchanged."""
        ...

    def update(self, document: Document) -> None:
        """Replace the metadata of a stored document: status, counts, failure reason."""
        ...

    def load_original(self, document_id: str) -> bytes:
        """The uploaded file as it was received."""
        ...

    def save_chunks(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        """Store the chunks of a parsed document, replacing earlier ones."""
        ...

    def load_chunks(self, document_id: str) -> list[Chunk]:
        """The stored chunks of a document; empty before it is parsed."""
        ...

    def get(self, document_id: str) -> Document | None:
        """The stored document with this id, or None."""
        ...
