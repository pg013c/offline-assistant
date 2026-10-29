import pytest

from assistant.adapters.fakes.document_parser import FakeDocumentParser
from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.fakes.ingestion_queue import FakeIngestionQueue
from assistant.adapters.keyword_index import KeywordChunkIndex
from assistant.domain.documents import Block, ChunkLocation, ParsedDocument
from assistant.domain.errors import FileTooLarge, NotUtf8Text, UnsupportedFileType
from assistant.services.documents import MAX_UPLOAD_BYTES, DocumentService

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
def index() -> KeywordChunkIndex:
    return KeywordChunkIndex()


@pytest.fixture
def queue() -> FakeIngestionQueue:
    return FakeIngestionQueue()


@pytest.fixture
def service(
    store: FakeDocumentStore, index: KeywordChunkIndex, queue: FakeIngestionQueue
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
    index: KeywordChunkIndex,
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
    index: KeywordChunkIndex,
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
    store: FakeDocumentStore, index: KeywordChunkIndex, queue: FakeIngestionQueue
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
    store: FakeDocumentStore, index: KeywordChunkIndex, queue: FakeIngestionQueue
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
    store: FakeDocumentStore, index: KeywordChunkIndex, queue: FakeIngestionQueue
) -> None:
    earlier = DocumentService(store, KeywordChunkIndex(), FakeDocumentParser(PARSED), queue)
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
