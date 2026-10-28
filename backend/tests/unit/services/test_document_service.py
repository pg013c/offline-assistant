import pytest

from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.keyword_index import KeywordChunkIndex
from assistant.domain.documents import Document, document_id_for
from assistant.domain.errors import FileTooLarge, NotUtf8Text, UnsupportedFileType
from assistant.services.documents import MAX_UPLOAD_BYTES, DocumentService

POLICY = b"Providers keep logs.\n\nAuthorities may inspect the logs."


@pytest.fixture
def store() -> FakeDocumentStore:
    return FakeDocumentStore()


@pytest.fixture
def index() -> KeywordChunkIndex:
    return KeywordChunkIndex()


@pytest.fixture
def service(store: FakeDocumentStore, index: KeywordChunkIndex) -> DocumentService:
    return DocumentService(store, index)


def test_upload_stores_and_indexes_the_document(
    service: DocumentService, store: FakeDocumentStore, index: KeywordChunkIndex
) -> None:
    document = service.upload("policy.txt", POLICY)

    assert document == Document(
        id=document_id_for(POLICY.decode()), title="policy", filename="policy.txt", chunk_count=2
    )
    assert store.list_documents() == [document]
    assert [result.chunk.text for result in index.search("inspect", limit=5)] == [
        "Authorities may inspect the logs."
    ]


def test_markdown_files_are_accepted(service: DocumentService) -> None:
    assert service.upload("notes.MD", b"# Notes").title == "notes"


def test_other_file_types_are_rejected(service: DocumentService, store: FakeDocumentStore) -> None:
    with pytest.raises(UnsupportedFileType):
        service.upload("policy.pdf", POLICY)

    assert store.list_documents() == []


def test_files_over_the_size_limit_are_rejected(
    store: FakeDocumentStore, index: KeywordChunkIndex
) -> None:
    service = DocumentService(store, index, max_upload_bytes=10)

    with pytest.raises(FileTooLarge):
        service.upload("policy.txt", b"x" * 11)

    assert store.list_documents() == []


def test_the_default_size_limit_is_five_megabytes() -> None:
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024


def test_text_that_is_not_utf8_is_rejected(
    service: DocumentService, store: FakeDocumentStore
) -> None:
    with pytest.raises(NotUtf8Text):
        service.upload("policy.txt", "Zażółć".encode("utf-16"))

    assert store.list_documents() == []


def test_uploading_the_same_content_twice_returns_the_existing_document(
    service: DocumentService, store: FakeDocumentStore, index: KeywordChunkIndex
) -> None:
    first = service.upload("policy.txt", POLICY)

    second = service.upload("copy of policy.txt", POLICY)

    assert second == first
    assert store.list_documents() == [first]
    assert len(index.search("inspect", limit=5)) == 1


def test_documents_lists_what_is_stored(service: DocumentService) -> None:
    document = service.upload("policy.txt", POLICY)

    assert service.list_documents() == [document]


def test_restore_indexes_previously_stored_documents(
    store: FakeDocumentStore, index: KeywordChunkIndex
) -> None:
    DocumentService(store, KeywordChunkIndex()).upload("policy.txt", POLICY)
    restarted = DocumentService(store, index)

    restored = restarted.restore()

    assert restored == 1
    assert len(index.search("inspect", limit=5)) == 1
