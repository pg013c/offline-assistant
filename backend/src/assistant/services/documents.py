import threading
from collections.abc import Callable
from dataclasses import replace
from pathlib import PurePath

import structlog

from assistant.domain.documents import (
    CHUNKER_VERSION,
    Chunk,
    Document,
    ParsedDocument,
    chunk_document,
    document_id_for,
    title_from_filename,
)
from assistant.domain.errors import (
    DocumentNotFound,
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


def _is_current(document: Document) -> bool:
    """Ready, with chunks cut by the chunker in use."""
    return document.status == "ready" and document.chunker_version == CHUNKER_VERSION


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
        # Uploads, deletes and ingestion jobs run on several threads; their reads and writes
        # of one document must not interleave.
        self._lock = threading.Lock()
        # The latest ingestion job queued for each document; older jobs write nothing.
        self._generations: dict[str, int] = {}

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
            job = self._new_job(document_id)
        self._queue.submit(job)
        # The queue may already have finished the job.
        return self._store.get(document_id) or document

    def ingest(self, document_id: str) -> None:
        """Parse, chunk and index a stored upload; record the outcome as its status."""
        self._ingest(document_id, self._generations.get(document_id))

    def _ingest(self, document_id: str, generation: int | None) -> None:
        """One ingestion job. It writes nothing once its document was deleted or queued again.

        Parsing and embedding run outside the lock, so a delete or re-index can happen
        meanwhile; every write is preceded by a check, under the lock, that the job is current.
        """
        with self._lock:
            document = self._current(document_id, generation)
        if document is None:
            return
        parsed = self._parse(document, generation)
        if parsed is None:
            return

        chunks = chunk_document(document_id, parsed)
        if not chunks:
            self._fail(document, generation, NO_TEXT)
            return
        with self._lock:
            if self._current(document_id, generation) is None:
                return
            self._store.save_chunks(document_id, chunks)
        try:
            self._index.add(chunks)
        except Exception:
            log.exception("document_ingestion_failed", document_id=document_id)
            with self._lock:
                # The write may have been applied in part; a failed document has no vectors.
                self._index.remove_document(document_id)
                if self._current(document_id, generation) is not None:
                    self._store.save_chunks(document_id, [])
            self._fail(document, generation, INGESTION_FAILED)
            return
        with self._lock:
            if self._current(document_id, generation) is None:
                # Deleted or queued again while embedding: these vectors are stale. The next
                # job for this document, if any, runs after this one and adds its own.
                self._index.remove_document(document_id)
                return
            self._store.update(
                replace(
                    document,
                    status="ready",
                    chunk_count=len(chunks),
                    page_count=parsed.page_count,
                    failure_reason=None,
                    chunker_version=CHUNKER_VERSION,
                )
            )
        log.info("document_ingested", document_id=document_id, chunks=len(chunks))

    def _parse(self, document: Document, generation: int | None) -> ParsedDocument | None:
        """The parsed document, or None after recording why it could not be parsed."""
        try:
            return self._parser.parse(document.filename, self._store.load_original(document.id))
        except DocumentUnreadable as error:
            self._fail(document, generation, error.reason)
        except Exception:
            log.exception("document_parsing_failed", document_id=document.id)
            self._fail(document, generation, UNREADABLE)
        return None

    def _current(self, document_id: str, generation: int | None) -> Document | None:
        """The document, if it is still processing and this job is its latest. Under the lock."""
        document = self._store.get(document_id)
        if document is None or document.status != "processing":
            return None
        if generation is not None and self._generations.get(document_id) != generation:
            return None
        return document

    def delete(self, document_id: str) -> None:
        """Remove a document, its files and its chunks from the index."""
        with self._lock:
            if self._store.get(document_id) is None:
                raise DocumentNotFound(document_id)
            self._index.remove_document(document_id)
            self._store.delete(document_id)
            # A job still running for it must not write it back.
            self._generations.pop(document_id, None)
        log.info("document_deleted", document_id=document_id)

    def reindex(self, document_id: str) -> Document:
        """Parse and index a stored document again; its chunk ids stay the same."""
        with self._lock:
            document = self._store.get(document_id)
            if document is None:
                raise DocumentNotFound(document_id)
            self._index.remove_document(document_id)
            processing = replace(document, status="processing", failure_reason=None)
            self._store.update(processing)
            job = self._new_job(document_id)
        self._queue.submit(job)
        # The queue may already have finished the job.
        return self._store.get(document_id) or processing

    def chunks(self, document_id: str) -> list[Chunk]:
        """The stored chunks of a document, in order."""
        if self._store.get(document_id) is None:
            raise DocumentNotFound(document_id)
        return self._store.load_chunks(document_id)

    def list_documents(self) -> list[Document]:
        """All stored documents."""
        return self._store.list_documents()

    def restore(self) -> int:
        """Bring the index in line with the store, and requeue unfinished documents.

        The index is derived from stored chunks: documents it lacks are added without parsing,
        and chunks of documents that are not ready, no longer stored, or cut by an older
        chunker are removed; the outdated ones are parsed again. Returns how many documents
        are searchable.
        """
        documents = self._store.list_documents()
        # Only documents ready and chunked by the current chunker may have vectors: drop those
        # of deleted, failed, unfinished or outdated ones.
        current_ids = {document.id for document in documents if _is_current(document)}
        for stale in self._index.document_ids() - current_ids:
            self._index.remove_document(stale)
        indexed = self._index.document_ids()
        ready = 0
        for document in documents:
            if _is_current(document) and document.id in indexed:
                ready += 1
                continue
            chunks = self._store.load_chunks(document.id) if _is_current(document) else []
            if chunks:
                self._index.add(chunks)
                ready += 1
            elif document.status != "failed":
                # Unfinished, ready without stored chunks, or cut by an older chunker: parse it
                # again.
                with self._lock:
                    if document.status == "ready":
                        self._store.update(replace(document, status="processing"))
                    job = self._new_job(document.id)
                self._queue.submit(job)
        return ready

    def _new_job(self, document_id: str) -> Callable[[], None]:
        """An ingestion job that supersedes any job made before for the document. Under the
        lock; submit the job after releasing it, since a queue may run it at once."""
        generation = self._generations.get(document_id, 0) + 1
        self._generations[document_id] = generation
        return lambda: self._ingest(document_id, generation)

    def _fail(self, document: Document, generation: int | None, reason: str) -> None:
        with self._lock:
            if self._current(document.id, generation) is None:
                return
            self._store.update(replace(document, status="failed", failure_reason=reason))
        log.info("document_failed", document_id=document.id, reason=reason)
