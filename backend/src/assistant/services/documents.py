from assistant.domain.documents import Document
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_store import DocumentStore

MAX_UPLOAD_BYTES = 0


class DocumentService:
    """Uploading, listing and restoring documents."""

    def __init__(
        self, store: DocumentStore, index: ChunkIndex, max_upload_bytes: int = MAX_UPLOAD_BYTES
    ) -> None:
        raise NotImplementedError

    def upload(self, filename: str, content: bytes) -> Document:
        """Validate, store and index an uploaded file; known content returns the stored document."""
        raise NotImplementedError

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        raise NotImplementedError

    def restore(self) -> int:
        """Index every stored document; returns how many were restored."""
        raise NotImplementedError
