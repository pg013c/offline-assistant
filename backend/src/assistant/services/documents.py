import threading
from dataclasses import replace
from pathlib import PurePath

import structlog

from assistant.domain.documents import (
    Document,
    chunk_document,
    document_id_for,
    title_from_filename,
)
from assistant.domain.errors import (
    DocumentUnreadable,
    FileTooLarge,
    NotUtf8Text,
    UnsupportedFileType,
)
from assistant.ports.chunk_index import ChunkIndex
from assistant.ports.document_parser import DocumentParser
from assistant.ports.document_store import DocumentStore
from assistant.ports.ingestion_queue import IngestionQueue

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
TEXT_EXTENSIONS = frozenset({".txt", ".md"})
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
# Shown when parsing fails for a reason the parser did not explain; details go to the log.
UNREADABLE = "The document could not be read."
NO_TEXT = "No text was found in the document."
INGESTION_FAILED = "The document could not be processed."

log = structlog.get_logger(__name__)


class DocumentService:
    """Uploading, ingesting, listing and restoring documents."""

    def __init__(
        self,
        store: DocumentStore,
        index: ChunkIndex,
        parser: DocumentParser,
        queue: IngestionQueue,
        max_upload_bytes: int = MAX_UPLOAD_BYTES,
    ) -> None:
        self._store = store
        self._index = index
        self._parser = parser
        self._queue = queue
        self._max_upload_bytes = max_upload_bytes
        # Uploads arrive on several threads; checking for a stored document and storing a new
        # one must not interleave.
        self._lock = threading.Lock()

    def upload(self, filename: str, content: bytes) -> Document:
        """Validate and store an upload, and queue its ingestion; known files return as stored."""
        extension = PurePath(filename).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise UnsupportedFileType(f"{filename}: supported file types are {supported}")
        if len(content) > self._max_upload_bytes:
            raise FileTooLarge(f"{filename}: larger than {self._max_upload_bytes} bytes")
        if extension in TEXT_EXTENSIONS:
            # Cheap to check now, so the user hears about it at once.
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise NotUtf8Text(f"{filename}: not valid UTF-8 text") from error

        document_id = document_id_for(content)
        with self._lock:
            existing = self._store.get(document_id)
            if existing is not None and existing.status != "failed":
                return existing
            if existing is not None:
                # A failure may have been temporary; uploading the file again retries it.
                document = replace(existing, status="processing", failure_reason=None)
                self._store.update(document)
            else:
                document = Document(
                    id=document_id,
                    title=title_from_filename(filename),
                    filename=filename,
                    chunk_count=0,
                    status="processing",
                )
                self._store.save_upload(document, content)
            self._queue_ingestion(document_id)
        # The queue may already have finished the job.
        return self._store.get(document_id) or document

    def ingest(self, document_id: str) -> None:
        """Parse, chunk and index a stored upload; record the outcome as its status."""
        document = self._store.get(document_id)
        # Only processing documents are ingested, so a job queued twice runs once.
        if document is None or document.status != "processing":
            return
        try:
            parsed = self._parser.parse(document.filename, self._store.load_original(document_id))
        except DocumentUnreadable as error:
            self._fail(document, error.reason)
            return
        except Exception:
            log.exception("document_parsing_failed", document_id=document_id)
            self._fail(document, UNREADABLE)
            return

        try:
            chunks = chunk_document(document_id, parsed)
            if not chunks:
                self._fail(document, NO_TEXT)
                return
            self._store.save_chunks(document_id, chunks)
            self._index.add(chunks)
        except Exception:
            log.exception("document_ingestion_failed", document_id=document_id)
            self._store.save_chunks(document_id, [])
            self._fail(document, INGESTION_FAILED)
            return
        self._store.update(
            replace(
                document,
                status="ready",
                chunk_count=len(chunks),
                page_count=parsed.page_count,
                failure_reason=None,
            )
        )
        log.info("document_ingested", document_id=document_id, chunks=len(chunks))

    def delete(self, document_id: str) -> None:
        """Remove a document, its files and its chunks from the index."""
        raise NotImplementedError

    def reindex(self, document_id: str) -> Document:
        """Parse and index a stored document again."""
        raise NotImplementedError

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        return self._store.list_documents()

    def restore(self) -> int:
        """Index stored chunks of ready documents and requeue unfinished ones.

        Returns how many documents were indexed.
        """
        ready = 0
        for document in self._store.list_documents():
            chunks = self._store.load_chunks(document.id) if document.status == "ready" else []
            if chunks:
                self._index.add(chunks)
                ready += 1
            elif document.status != "failed":
                # Unfinished, or ready without stored chunks: parse it again.
                if document.status == "ready":
                    self._store.update(replace(document, status="processing"))
                self._queue_ingestion(document.id)
        return ready

    def _queue_ingestion(self, document_id: str) -> None:
        self._queue.submit(lambda: self.ingest(document_id))

    def _fail(self, document: Document, reason: str) -> None:
        self._store.update(replace(document, status="failed", failure_reason=reason))
        log.info("document_failed", document_id=document.id, reason=reason)
