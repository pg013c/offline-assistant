from collections.abc import Callable, Sequence
from dataclasses import replace

import pytest

from assistant.adapters.fakes.chunk_index import InMemoryChunkIndex
from assistant.adapters.fakes.document_parser import FakeDocumentParser
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import FakeIngestionQueue
from assistant.domain.documents import (
    CHUNKER_VERSION,
    Block,
    Chunk,
    ChunkLocation,
    Document,
    ParsedDocument,
)
from assistant.domain.errors import (
    DocumentNotFound,
    DocumentUnreadable,
    FileTooLarge,
    NotUtf8Text,
    UnsupportedFileType,
)
from assistant.services.documents import INGESTION_FAILED, MAX_UPLOAD_BYTES, DocumentService

PDF = b"%PDF-1.7 policy"
PARSED = ParsedDocument(
    page_count=3,
    blocks=(
        Block(kind="heading", text="Article 12", page=2, level=1),
        Block(kind="paragraph", text="1. Providers keep logs.", page=2),
        Block(kind="paragraph", text="2. Authorities may inspect the logs.", page=3),
    ),
)


class ParserThatMustNotRun:
    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise AssertionError("restore must not parse again")


class BrokenParser:
    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        raise RuntimeError("model crashed")


@pytest.fixture
def store() -> FakeDocumentStore:
    return FakeDocumentStore()


@pytest.fixture
def index() -> InMemoryChunkIndex:
    return InMemoryChunkIndex()


@pytest.fixture
def queue() -> FakeIngestionQueue:
    return FakeIngestionQueue()


@pytest.fixture
def service(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> DocumentService:
    parser = FakeDocumentParser(PARSED, unreadable={"locked.pdf": "The PDF is password-protected."})
    return DocumentService(store, index, parser, queue)


def test_upload_stores_the_file_and_returns_it_as_processing(
    service: DocumentService, store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    document = service.upload("AI Act.pdf", PDF)

    assert (document.title, document.filename, document.status) == (
        "AI Act",
        "AI Act.pdf",
        "processing",
    )
    assert document.chunk_count == 0
    assert store.load_original(document.id) == PDF
    assert queue.pending == 1


def test_ingestion_makes_the_document_ready_and_searchable(
    service: DocumentService,
    store: FakeDocumentStore,
    index: InMemoryChunkIndex,
    queue: FakeIngestionQueue,
) -> None:
    document = service.upload("AI Act.pdf", PDF)

    queue.run_all()

    ready = store.get(document.id)
    assert ready is not None
    assert (ready.status, ready.chunk_count, ready.page_count) == ("ready", 2, 3)
    [result] = index.search("inspect", limit=5)
    assert result.chunk.location == ChunkLocation(
        heading_path=("Article 12",), article="12", paragraph="2", page=3
    )
    assert [chunk.text for chunk in store.load_chunks(document.id)] == [
        "1. Providers keep logs.",
        "2. Authorities may inspect the logs.",
    ]


def test_an_unreadable_file_fails_with_its_reason_and_nothing_is_searchable(
    service: DocumentService,
    store: FakeDocumentStore,
    index: InMemoryChunkIndex,
    queue: FakeIngestionQueue,
) -> None:
    document = service.upload("locked.pdf", PDF)

    queue.run_all()

    failed = store.get(document.id)
    assert failed is not None
    assert (failed.status, failed.failure_reason) == ("failed", "The PDF is password-protected.")
    assert index.search("inspect", limit=5) == []
    assert store.load_chunks(document.id) == []


def test_an_unexpected_parser_error_fails_the_document_without_internals(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    service = DocumentService(store, index, BrokenParser(), queue)
    document = service.upload("policy.pdf", PDF)

    queue.run_all()

    failed = store.get(document.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.failure_reason == "The document could not be read."


@pytest.mark.parametrize(
    "filename", ["a.pdf", "b.DOCX", "c.png", "d.jpg", "e.jpeg", "f.txt", "g.md"]
)
def test_supported_file_types_are_accepted(service: DocumentService, filename: str) -> None:
    assert service.upload(filename, PDF + filename.encode()).status == "processing"


def test_other_file_types_are_rejected_and_nothing_is_stored(
    service: DocumentService, store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    with pytest.raises(UnsupportedFileType):
        service.upload("slides.pptx", PDF)

    assert store.list_documents() == []
    assert queue.pending == 0


def test_files_over_the_size_limit_are_rejected(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    service = DocumentService(store, index, FakeDocumentParser(PARSED), queue, max_upload_bytes=10)

    with pytest.raises(FileTooLarge):
        service.upload("policy.pdf", b"x" * 11)

    assert store.list_documents() == []


def test_the_default_size_limit_is_fifty_megabytes() -> None:
    assert MAX_UPLOAD_BYTES == 50 * 1024 * 1024


def test_text_files_that_are_not_utf8_are_rejected_at_upload(
    service: DocumentService, store: FakeDocumentStore
) -> None:
    with pytest.raises(NotUtf8Text):
        service.upload("policy.txt", "Zażółć".encode("utf-16"))

    assert store.list_documents() == []


def test_uploading_the_same_file_twice_returns_the_stored_document(
    service: DocumentService, store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    first = service.upload("policy.pdf", PDF)
    queue.run_all()

    second = service.upload("copy of policy.pdf", PDF)

    assert second == store.get(first.id)
    assert second.status == "ready"
    assert len(store.list_documents()) == 1
    assert queue.pending == 0


def test_documents_lists_what_is_stored(service: DocumentService) -> None:
    document = service.upload("policy.pdf", PDF)

    assert service.list_documents() == [document]


def test_restore_indexes_stored_chunks_without_parsing_and_resubmits_unfinished_files(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    earlier = DocumentService(store, InMemoryChunkIndex(), FakeDocumentParser(PARSED), queue)
    ready = earlier.upload("ready.pdf", PDF)
    queue.run_all()
    unfinished = earlier.upload("unfinished.pdf", PDF + b"2")
    restarted_queue = FakeIngestionQueue()
    restarted = DocumentService(store, index, ParserThatMustNotRun(), restarted_queue)

    restored = restarted.restore()

    assert restored == 1
    assert len(index.search("inspect", limit=5)) == 1
    assert restarted_queue.pending == 1
    assert store.get(ready.id) is not None
    assert unfinished.status == "processing"


class FailingIndex(InMemoryChunkIndex):
    def add(self, chunks: Sequence[Chunk]) -> None:
        raise OSError("disk full")


class FlakyParser:
    """Fails the first time, then reads the document."""

    def __init__(self) -> None:
        self.calls = 0

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        self.calls += 1
        if self.calls == 1:
            raise DocumentUnreadable("Tesseract has no Polish language data.")
        return PARSED


def test_a_failure_after_parsing_fails_the_document(
    store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    service = DocumentService(store, FailingIndex(), FakeDocumentParser(PARSED), queue)
    document = service.upload("policy.pdf", PDF)

    queue.run_all()

    failed = store.get(document.id)
    assert failed is not None
    assert (failed.status, failed.failure_reason) == ("failed", INGESTION_FAILED)
    assert store.load_chunks(document.id) == []


def test_uploading_a_failed_document_again_retries_it(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    parser = FlakyParser()
    service = DocumentService(store, index, parser, queue)
    first = service.upload("policy.pdf", PDF)
    queue.run_all()

    retried = service.upload("policy.pdf", PDF)
    queue.run_all()

    assert retried.status == "processing"
    ready = store.get(first.id)
    assert ready is not None
    assert (ready.status, ready.failure_reason) == ("ready", None)
    assert len(index.search("inspect", limit=5)) == 1


def test_ingesting_a_document_that_is_not_processing_changes_nothing(
    service: DocumentService, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    document = service.upload("policy.pdf", PDF)
    queue.run_all()

    service.ingest(document.id)

    assert len(index.search("inspect", limit=5)) == 1


def test_restore_requeues_a_ready_document_without_stored_chunks(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    # Documents stored by F-01 have metadata but no chunks file.
    store.save_upload(
        Document(id="f01", title="old", filename="old.txt", chunk_count=2, status="ready"),
        b"Providers keep logs.\n\nAuthorities may inspect the logs.",
    )
    service = DocumentService(store, index, FakeDocumentParser(PARSED), queue)

    restored = service.restore()
    queue.run_all()

    assert restored == 0
    document = store.get("f01")
    assert document is not None
    assert document.status == "ready"
    assert len(index.search("inspect", limit=5)) == 1


class CountingIndex(InMemoryChunkIndex):
    def __init__(self) -> None:
        super().__init__()
        self.added: list[str] = []

    def add(self, chunks: Sequence[Chunk]) -> None:
        self.added.extend(chunk.document_id for chunk in chunks)
        super().add(chunks)


def test_deleting_a_document_removes_it_from_store_and_index(
    service: DocumentService,
    store: FakeDocumentStore,
    index: InMemoryChunkIndex,
    queue: FakeIngestionQueue,
) -> None:
    document = service.upload("policy.pdf", PDF)
    queue.run_all()

    service.delete(document.id)

    assert store.get(document.id) is None
    assert index.document_ids() == set()


def test_deleting_or_reindexing_an_unknown_document_is_refused(service: DocumentService) -> None:
    with pytest.raises(DocumentNotFound):
        service.delete("unknown")
    with pytest.raises(DocumentNotFound):
        service.reindex("unknown")


def test_reindexing_parses_the_document_again_and_keeps_its_chunk_ids(
    service: DocumentService,
    store: FakeDocumentStore,
    index: InMemoryChunkIndex,
    queue: FakeIngestionQueue,
) -> None:
    document = service.upload("policy.pdf", PDF)
    queue.run_all()
    before = [chunk.id for chunk in store.load_chunks(document.id)]

    reindexing = service.reindex(document.id)

    assert reindexing.status == "processing"
    assert index.document_ids() == set()
    queue.run_all()
    ready = store.get(document.id)
    assert ready is not None
    assert ready.status == "ready"
    assert [chunk.id for chunk in store.load_chunks(document.id)] == before
    assert index.document_ids() == {document.id}


def test_restore_adds_only_missing_documents_and_drops_deleted_ones(
    store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    earlier = DocumentService(store, InMemoryChunkIndex(), FakeDocumentParser(PARSED), queue)
    indexed = earlier.upload("indexed.pdf", PDF)
    missing = earlier.upload("missing.pdf", PDF + b"2")
    queue.run_all()
    index = CountingIndex()
    index.add(store.load_chunks(indexed.id))
    index.add([Chunk(id="ghost:0", document_id="ghost", position=0, text="Deleted.")])
    index.added.clear()
    restarted = DocumentService(store, index, ParserThatMustNotRun(), queue)

    restarted.restore()

    assert index.document_ids() == {indexed.id, missing.id}
    assert set(index.added) == {missing.id}


class ParserThatActsMidway:
    """Runs an action, as another request would, while the document is being parsed."""

    def __init__(self) -> None:
        self.during_parse: list[Callable[[], object]] = []
        self.calls = 0

    def parse(self, filename: str, content: bytes) -> ParsedDocument:
        self.calls += 1
        if self.during_parse:
            self.during_parse.pop(0)()
        return PARSED


def test_a_document_deleted_while_it_is_parsed_stays_deleted(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    parser = ParserThatActsMidway()
    service = DocumentService(store, index, parser, queue)
    document = service.upload("policy.pdf", PDF)
    parser.during_parse.append(lambda: service.delete(document.id))

    queue.run_all()

    assert store.get(document.id) is None
    assert store.load_chunks(document.id) == []
    assert index.document_ids() == set()


def test_a_document_reindexed_while_it_is_parsed_is_parsed_again_and_indexed_once(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    parser = ParserThatActsMidway()
    service = DocumentService(store, index, parser, queue)
    document = service.upload("policy.pdf", PDF)
    parser.during_parse.append(lambda: service.reindex(document.id))

    queue.run_all()

    ready = store.get(document.id)
    assert ready is not None
    assert ready.status == "ready"
    assert parser.calls == 2
    assert len(index.search("inspect", limit=10)) == 1


def test_a_deleted_document_is_not_written_back_as_failed(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    service = DocumentService(store, index, BrokenParser(), queue)
    document = service.upload("policy.pdf", PDF)
    service.delete(document.id)

    queue.run_all()

    assert store.get(document.id) is None


class PartlyWritingIndex(InMemoryChunkIndex):
    """Stores the chunks, then reports a failure, as a timed-out write that was applied."""

    def add(self, chunks: Sequence[Chunk]) -> None:
        super().add(chunks)
        raise OSError("timed out")


def test_a_document_that_failed_while_indexing_leaves_no_vectors(
    store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    index = PartlyWritingIndex()
    service = DocumentService(store, index, FakeDocumentParser(PARSED), queue)
    document = service.upload("policy.pdf", PDF)

    queue.run_all()

    failed = store.get(document.id)
    assert failed is not None
    assert failed.status == "failed"
    assert index.document_ids() == set()


def test_restore_removes_vectors_of_documents_that_are_not_ready(
    store: FakeDocumentStore, index: InMemoryChunkIndex, queue: FakeIngestionQueue
) -> None:
    store.save_upload(
        Document(
            id="bad",
            title="bad",
            filename="bad.pdf",
            chunk_count=0,
            status="failed",
            failure_reason="The PDF is password-protected.",
        ),
        PDF,
    )
    index.add([Chunk(id="bad:0", document_id="bad", position=0, text="Stale vectors.")])
    service = DocumentService(store, index, FakeDocumentParser(PARSED), queue)

    service.restore()

    assert index.document_ids() == set()


def test_a_document_lists_its_stored_chunks(
    service: DocumentService, queue: FakeIngestionQueue
) -> None:
    document = service.upload("policy.pdf", PDF)
    queue.run_all()

    chunks = service.chunks(document.id)

    assert [
        (chunk.position, chunk.location.article, chunk.location.paragraph) for chunk in chunks
    ] == [
        (0, "12", "1"),
        (1, "12", "2"),
    ]


def test_listing_the_chunks_of_an_unknown_document_is_refused(service: DocumentService) -> None:
    with pytest.raises(DocumentNotFound):
        service.chunks("unknown")


def test_ingestion_records_the_chunker_version(
    service: DocumentService, store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    document = service.upload("policy.pdf", PDF)

    queue.run_all()

    ready = store.get(document.id)
    assert ready is not None
    assert ready.chunker_version == CHUNKER_VERSION


@pytest.mark.parametrize("version", [None, CHUNKER_VERSION - 1])
def test_restore_parses_again_documents_chunked_by_another_chunker(
    store: FakeDocumentStore, queue: FakeIngestionQueue, version: int | None
) -> None:
    earlier = DocumentService(store, InMemoryChunkIndex(), FakeDocumentParser(PARSED), queue)
    document = earlier.upload("policy.pdf", PDF)
    queue.run_all()
    stored = store.get(document.id)
    assert stored is not None
    store.update(replace(stored, chunker_version=version))
    index = InMemoryChunkIndex()
    index.add(store.load_chunks(document.id))
    restarted = DocumentService(store, index, FakeDocumentParser(PARSED), queue)

    restarted.restore()

    assert index.document_ids() == set()
    queue.run_all()
    ready = store.get(document.id)
    assert ready is not None
    assert (ready.status, ready.chunker_version) == ("ready", CHUNKER_VERSION)
    assert index.document_ids() == {document.id}


def test_restore_does_not_parse_documents_of_the_current_chunker(
    store: FakeDocumentStore, queue: FakeIngestionQueue
) -> None:
    earlier = DocumentService(store, InMemoryChunkIndex(), FakeDocumentParser(PARSED), queue)
    document = earlier.upload("policy.pdf", PDF)
    queue.run_all()
    restarted = DocumentService(store, InMemoryChunkIndex(), ParserThatMustNotRun(), queue)

    restarted.restore()
    queue.run_all()

    assert restarted.list_documents()[0].id == document.id
