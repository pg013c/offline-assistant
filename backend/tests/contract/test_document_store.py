"""Contract for the DocumentStore port; every adapter must pass it."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.domain.documents import Chunk, ChunkLocation, Document
from assistant.ports.document_store import DocumentStore

ADAPTERS: list[Callable[[Path], DocumentStore]] = [
    lambda _: FakeDocumentStore(),
    LocalFileDocumentStore,
]

POLICY = Document(
    id="a1", title="policy", filename="policy.pdf", chunk_count=0, status="processing"
)
NOTES = Document(id="b2", title="notes", filename="notes.md", chunk_count=0, status="processing")
POLICY_READY = replace(POLICY, status="ready", chunk_count=2, page_count=3)
CHUNKS = [
    Chunk(
        id="a1:0",
        document_id="a1",
        position=0,
        text="1. Providers shall keep logs.",
        location=ChunkLocation(
            heading_path=("Chapter III", "Article 6"), article="6", paragraph="1", page=2
        ),
    ),
    Chunk(id="a1:1", document_id="a1", position=1, text="Plain text."),
]


@pytest.fixture(params=ADAPTERS, ids=["fake", "local-file"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> DocumentStore:
    factory: Callable[[Path], DocumentStore] = request.param
    return factory(tmp_path)


def test_uploads_are_listed_and_fetched_by_id(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")
    store.save_upload(NOTES, b"Notes.")

    assert sorted(store.list_documents(), key=lambda document: document.id) == [POLICY, NOTES]
    assert store.get(POLICY.id) == POLICY
    assert store.get("unknown") is None


def test_the_original_file_is_kept(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")

    assert store.load_original(POLICY.id) == b"%PDF policy"


def test_saving_the_same_upload_twice_keeps_one(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")
    store.save_upload(POLICY, b"%PDF policy")

    assert store.list_documents() == [POLICY]


def test_update_changes_status_and_counts(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")

    store.update(POLICY_READY)

    assert store.get(POLICY.id) == POLICY_READY
    assert store.list_documents() == [POLICY_READY]


def test_a_failed_document_keeps_its_reason(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")
    failed = replace(POLICY, status="failed", failure_reason="The PDF is password-protected.")

    store.update(failed)

    assert store.get(POLICY.id) == failed


def test_saved_chunks_load_back_with_their_locations(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")

    store.save_chunks(POLICY.id, CHUNKS)

    assert store.load_chunks(POLICY.id) == CHUNKS


def test_a_document_without_chunks_loads_none(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")

    assert store.load_chunks(POLICY.id) == []


def test_an_empty_store_lists_nothing(store: DocumentStore) -> None:
    assert store.list_documents() == []


def test_deleting_a_document_removes_its_metadata_original_and_chunks(
    store: DocumentStore,
) -> None:
    store.save_upload(POLICY, b"%PDF policy")
    store.save_chunks(POLICY.id, CHUNKS)
    store.save_upload(NOTES, b"Notes.")

    store.delete(POLICY.id)

    assert store.get(POLICY.id) is None
    assert store.list_documents() == [NOTES]
    assert store.load_chunks(POLICY.id) == []


def test_deleting_twice_or_an_unknown_document_is_harmless(store: DocumentStore) -> None:
    store.save_upload(POLICY, b"%PDF policy")
    store.delete(POLICY.id)

    store.delete(POLICY.id)
    store.delete("unknown")

    assert store.list_documents() == []
