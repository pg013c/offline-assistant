"""In-memory DocumentStore for tests."""

from collections.abc import Sequence

from assistant.domain.documents import Chunk, Document


class FakeDocumentStore:
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}
        self._originals: dict[str, bytes] = {}
        self._chunks: dict[str, list[Chunk]] = {}

    def save_upload(self, document: Document, content: bytes) -> None:
        if document.id not in self._documents:
            self._documents[document.id] = document
            self._originals[document.id] = content

    def update(self, document: Document) -> None:
        self._documents[document.id] = document

    def load_original(self, document_id: str) -> bytes:
        return self._originals[document_id]

    def save_chunks(self, document_id: str, chunks: Sequence[Chunk]) -> None:
        self._chunks[document_id] = list(chunks)

    def load_chunks(self, document_id: str) -> list[Chunk]:
        return list(self._chunks.get(document_id, []))

    def list_documents(self) -> list[Document]:
        return list(self._documents.values())

    def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)
