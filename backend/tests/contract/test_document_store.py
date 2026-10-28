"""Contract for the DocumentStore port; every adapter must pass it."""

from collections.abc import Callable
from pathlib import Path

import pytest

from assistant.adapters.fakes.document_store import FakeDocumentStore
from assistant.adapters.file_document_store import LocalFileDocumentStore
from assistant.domain.documents import Document
from assistant.ports.document_store import DocumentStore

ADAPTERS: list[Callable[[Path], DocumentStore]] = [
    lambda _: FakeDocumentStore(),
    LocalFileDocumentStore,
]

POLICY = Document(id="a1", title="policy", filename="policy.txt", chunk_count=2)
NOTES = Document(id="b2", title="notes", filename="notes.md", chunk_count=1)


@pytest.fixture(params=ADAPTERS, ids=["fake", "local-file"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> DocumentStore:
    factory: Callable[[Path], DocumentStore] = request.param
    return factory(tmp_path)


def test_saved_documents_are_listed(store: DocumentStore) -> None:
    store.save(POLICY, "Policy text.")
    store.save(NOTES, "Notes.")

    assert sorted(store.list_documents(), key=lambda document: document.id) == [POLICY, NOTES]


def test_saved_documents_load_with_their_text(store: DocumentStore) -> None:
    store.save(POLICY, "Policy text.\n\nSecond part.")

    assert store.load_all() == [(POLICY, "Policy text.\n\nSecond part.")]


def test_saving_the_same_document_twice_keeps_one(store: DocumentStore) -> None:
    store.save(POLICY, "Policy text.")
    store.save(POLICY, "Policy text.")

    assert store.list_documents() == [POLICY]


def test_an_empty_store_lists_nothing(store: DocumentStore) -> None:
    assert store.list_documents() == []
    assert store.load_all() == []


def test_a_document_can_be_fetched_by_id(store: DocumentStore) -> None:
    store.save(POLICY, "Policy text.")

    assert store.get(POLICY.id) == POLICY
    assert store.get("unknown") is None
