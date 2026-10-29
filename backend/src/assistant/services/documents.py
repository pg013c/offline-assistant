from pathlib import PurePath

from assistant.domain.documents import (
    Document,
    document_id_for,
    split_into_chunks,
    title_from_filename,
)
from assistant.domain.errors import FileTooLarge, NotUtf8Text, UnsupportedFileType
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_store import DocumentStore

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
SUPPORTED_EXTENSIONS = frozenset({".txt", ".md"})


class DocumentService:
    """Uploading, listing and restoring documents."""

    def __init__(
        self, store: DocumentStore, index: ChunkIndex, max_upload_bytes: int = MAX_UPLOAD_BYTES
    ) -> None:
        self._store = store
        self._index = index
        self._max_upload_bytes = max_upload_bytes

    def upload(self, filename: str, content: bytes) -> Document:
        """Validate, store and index an uploaded file; known content returns the stored document."""
        extension = PurePath(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileType(f"{filename}: only .txt and .md files are supported")
        if len(content) > self._max_upload_bytes:
            raise FileTooLarge(f"{filename}: larger than {self._max_upload_bytes} bytes")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise NotUtf8Text(f"{filename}: not valid UTF-8 text") from error

        document_id = document_id_for(text)
        existing = self._store.get(document_id)
        if existing is not None:
            return existing

        chunks = split_into_chunks(document_id, text)
        document = Document(
            id=document_id,
            title=title_from_filename(filename),
            filename=filename,
            chunk_count=len(chunks),
        )
        self._store.save_upload(document, content)
        self._store.save_chunks(document_id, chunks)
        self._index.add(chunks)
        return document

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        return self._store.list_documents()

    def restore(self) -> int:
        """Index every stored document; returns how many were restored."""
        ready = [
            document for document in self._store.list_documents() if document.status == "ready"
        ]
        for document in ready:
            self._index.add(self._store.load_chunks(document.id))
        return len(ready)
